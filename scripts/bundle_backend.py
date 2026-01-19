import os
import subprocess
import sys
import platform
import shutil
from pathlib import Path

def get_target_triple():
    # Use rustc to get the host triple as it's the most reliable for Tauri
    try:
        output = subprocess.check_output(["rustc", "-vV"], text=True)
        for line in output.splitlines():
            if line.startswith("host:"):
                return line.split(":")[1].strip()
    except Exception:
        # Fallback to a best guess if rustc is not available
        system = platform.system().lower()
        machine = platform.machine().lower()
        if system == "darwin":
            if machine == "arm64":
                return "aarch64-apple-darwin"
            return "x86_64-apple-darwin"
        elif system == "windows":
            return "x86_64-pc-windows-msvc"
        elif system == "linux":
            return "x86_64-unknown-linux-gnu"
    return f"unknown-{platform.system().lower()}"

def bundle():
    print("🚀 Starting backend bundling process...")
    
    root_dir = Path(__file__).parent.parent.absolute()
    os.chdir(root_dir)
    
    target_triple = get_target_triple()
    binary_name = f"vibe-{target_triple}"
    if platform.system() == "Windows":
        binary_name += ".exe"
        
    dist_dir = root_dir / "frontend" / "src-tauri" / "bin"
    dist_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📦 Target triple: {target_triple}")
    print(f"📂 Output directory: {dist_dir}")
    
    # Install PyInstaller if not present
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Define the PyInstaller command
    # --onefile: package into a single executable
    # --name: name of the output binary
    # --add-data: include the vibe-templates directory
    # vibe_tools/cli.py is the entry point
    
    separator = ";" if platform.system() == "Windows" else ":"
    
    # We need to find where vibe-templates is. It should be in the root.
    templates_src = root_dir / "vibe-templates"
    
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", binary_name,
        f"--add-data={templates_src}{separator}vibe-templates",
        "vibe_tools/cli.py"
    ]
    
    print(f"🛠️ Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    
    # Move the binary to the Tauri bin directory
    src_binary = root_dir / "dist" / binary_name
    dest_binary = dist_dir / binary_name
    
    if dest_binary.exists():
        dest_binary.unlink()
        
    shutil.move(str(src_binary), str(dest_binary))
    
    print(f"✅ Backend bundled successfully: {dest_binary}")

if __name__ == "__main__":
    bundle()
