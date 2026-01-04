import pytest
import pytest_asyncio
from httpx import AsyncClient
from tortoise import Tortoise

from src.core.db import TORTOISE_ORM
from src.main import app
from src.models.audit_log import AuditLog
from src.models.candidate import Candidate
from src.models.person import Person
from src.models.project import Project
from src.models.tenant import Tenant


@pytest_asyncio.fixture(autouse=True)
async def initialize_tests():
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()
    yield
    await Tortoise._drop_databases()
    await Tortoise.close_connections()

@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Casting OS API is running"}

@pytest.mark.asyncio
async def test_auth_failure():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/projects/")
    assert response.status_code == 422 # Missing header

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/projects/", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_tenant_isolation():
    t1 = await Tenant.create(name="Tenant 1", api_key="key1")
    t2 = await Tenant.create(name="Tenant 2", api_key="key2")

    await Project.create(title="Project 1", tenant=t1)
    await Project.create(title="Project 2", tenant=t2)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # T1 should only see Project 1
        resp1 = await ac.get("/api/projects/", headers={"X-API-Key": "key1"})
        assert resp1.status_code == 200
        assert len(resp1.json()) == 1
        assert resp1.json()[0]["title"] == "Project 1"

        # T2 should only see Project 2
        resp2 = await ac.get("/api/projects/", headers={"X-API-Key": "key2"})
        assert resp2.status_code == 200
        assert len(resp2.json()) == 1
        assert resp2.json()[0]["title"] == "Project 2"

@pytest.mark.asyncio
async def test_person_gdpr():
    await Tenant.create(name="T1", api_key="key1")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/people/", headers={"X-API-Key": "key1"}, json={
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@example.com",
            "gdpr_consent": True
        })
    assert response.status_code == 200
    data = response.json()
    assert data["gdpr_consent"] is True

@pytest.mark.asyncio
async def test_audition_scheduling():
    t1 = await Tenant.create(name="T1", api_key="key1")
    p1 = await Project.create(title="Project 1", tenant=t1)
    person = await Person.create(first_name="Actor", last_name="1", email="actor@example.com")

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 1. Create candidate
        cand_resp = await ac.post("/api/candidates/", headers={"X-API-Key": "key1"}, json={
            "project_id": str(p1.id),
            "person_id": str(person.id)
        })
        cand_id = cand_resp.json()["id"]

        # 2. Schedule audition
        aud_resp = await ac.post("/api/auditions/", headers={"X-API-Key": "key1"}, json={
            "project_id": str(p1.id),
            "candidate_id": cand_id,
            "type": "selftape"
        })
        assert aud_resp.status_code == 200
        assert aud_resp.json()["type"] == "selftape"


@pytest.mark.asyncio
async def test_tenant_leakage_prevention():
    await Tenant.create(name="Tenant 1", api_key="key1")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Should NOT be able to list tenants
        response = await ac.get("/api/tenants/")
        assert response.status_code == 405 # Method not allowed or 404 since we changed router

@pytest.mark.asyncio
async def test_people_directory_leakage_prevention():
    await Tenant.create(name="T1", api_key="key1")
    await Person.create(first_name="Secret", last_name="Person", email="secret@example.com")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Listing without email should return empty
        response = await ac.get("/api/people/", headers={"X-API-Key": "key1"})
        assert response.status_code == 200
        assert len(response.json()) == 0

@pytest.mark.asyncio
async def test_cross_project_candidate_audition_prevention():
    t1 = await Tenant.create(name="T1", api_key="key1")
    p1 = await Project.create(title="P1", tenant=t1)
    p2 = await Project.create(title="P2", tenant=t1)
    person = await Person.create(first_name="A", last_name="B", email="a@b.com")

    # Candidate in P1
    c1 = await Candidate.create(project=p1, person=person)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Try to create audition in P2 for candidate from P1
        response = await ac.post("/api/auditions/", headers={"X-API-Key": "key1"}, json={
            "project_id": str(p2.id),
            "candidate_id": str(c1.id),
            "type": "in-person"
        })
        assert response.status_code == 400
        assert "Candidate does not belong to this project" in response.json()["detail"]

@pytest.mark.asyncio
async def test_gdpr_right_to_delete():
    await Tenant.create(name="T1", api_key="key1")
    p = await Person.create(first_name="Delete", last_name="Me", email="delete@me.com")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Now returns 403 as tenants cannot hard-delete people globally
        response = await ac.delete(f"/api/people/{p.id}", headers={"X-API-Key": "key1"})
        assert response.status_code == 403

@pytest.mark.asyncio
async def test_candidate_deletion():
    t1 = await Tenant.create(name="T1", api_key="key1")
    p1 = await Project.create(title="P1", tenant=t1)
    person = await Person.create(first_name="A", last_name="B", email="a@b.com")
    c1 = await Candidate.create(project=p1, person=person)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.delete(f"/api/candidates/{c1.id}", headers={"X-API-Key": "key1"})
        assert response.status_code == 204

    assert await Candidate.get_or_none(id=c1.id) is None
    assert await Person.get_or_none(id=person.id) is not None # Person remains globally

@pytest.mark.asyncio
async def test_unauthorized_person_access():
    await Tenant.create(name="T1", api_key="key1")
    t2 = await Tenant.create(name="T2", api_key="key2")
    person = await Person.create(first_name="Secret", last_name="Person", email="secret@example.com")

    # Linked to T2
    p2 = await Project.create(title="P2", tenant=t2)
    await Candidate.create(project=p2, person=person)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # T1 should NOT be able to access person details
        response = await ac.get(f"/api/people/{person.id}", headers={"X-API-Key": "key1"})
        assert response.status_code == 403

@pytest.mark.asyncio
async def test_client_review_portal():
    t1 = await Tenant.create(name="T1", api_key="key1")
    p1 = await Project.create(title="P1", tenant=t1)
    person = await Person.create(first_name="Actor", last_name="X", email="x@example.com")
    await Candidate.create(
        project=p1,
        person=person,
        shared_with_client=True,
        tenant_notes="INTERNAL ONLY",
        client_notes="HELLO CLIENT"
    )

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 1. Get token
        token_resp = await ac.post(f"/api/clients/token/{p1.id}", headers={"X-API-Key": "key1"})
        assert token_resp.status_code == 200
        token = token_resp.json()

        # 2. Access with token
        response = await ac.get(f"/api/clients/review/{token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "tenant_notes" not in data[0]
        assert data[0]["client_notes"] == "HELLO CLIENT"

        # 3. Access without token/wrong token fails
        resp_bad = await ac.get("/api/clients/review/wrong-token")
        assert resp_bad.status_code == 404

@pytest.mark.asyncio
async def test_audit_logging():
    t1 = await Tenant.create(name="T1", api_key="key1")
    p1 = await Project.create(title="P1", tenant=t1)
    person = await Person.create(first_name="A", last_name="B", email="a@b.com")

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create candidate triggers audit log
        await ac.post("/api/candidates/", headers={"X-API-Key": "key1"}, json={
            "project_id": str(p1.id),
            "person_id": str(person.id)
        })

    logs = await AuditLog.filter(tenant=t1, action="candidate_created")
    assert len(logs) == 1

@pytest.mark.asyncio
async def test_ads_and_intake():
    t1 = await Tenant.create(name="T1", api_key="key1")
    p1 = await Project.create(title="P1", tenant=t1)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create Ad
        ad_resp = await ac.post("/api/ads/", headers={"X-API-Key": "key1"}, json={
            "project_id": str(p1.id),
            "title": "Open Call",
            "description": "Apply now"
        })
        assert ad_resp.status_code == 200
        ad_id = ad_resp.json()["id"]

        # Public Intake
        intake_resp = await ac.post(f"/api/intake/apply/{ad_id}", json={
            "first_name": "Applicant",
            "last_name": "One",
            "email": "app1@example.com"
        })
        assert intake_resp.status_code == 200
        assert intake_resp.json()["status"] == "applied"

@pytest.mark.asyncio
async def test_candidate_update():
    t1 = await Tenant.create(name="T1", api_key="key1")
    p1 = await Project.create(title="P1", tenant=t1)
    person = await Person.create(first_name="A", last_name="B", email="a@b.com")
    c1 = await Candidate.create(project=p1, person=person, status="pending")

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.patch(f"/api/candidates/{c1.id}", headers={"X-API-Key": "key1"}, json={
            "status": "shortlisted",
            "shared_with_client": True
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "shortlisted"
        assert data["shared_with_client"] is True
