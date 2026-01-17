import hljs from 'highlight.js';

/**
 * VanillaPRDEditor - A vanilla JavaScript Markdown editor for PRDs.
 * Isolated from React rendering to ensure selection stability and performance.
 */

export class VanillaPRDEditor {
  private container: HTMLDivElement;
  private toolbar: HTMLDivElement;
  private editor: HTMLDivElement;
  private onChange: (content: string) => void;
  private onSave?: () => void;
  private isFocused: boolean = false;
  private contextMenu: HTMLDivElement | null = null;
  private accentColor: string;
  private isDark: boolean;

  constructor(
    container: HTMLDivElement,
    initialContent: string,
    onChange: (content: string) => void,
    onSave?: () => void,
    accentColor: string = '#10b981',
    isDark: boolean = false
  ) {
    this.container = container;
    this.onChange = onChange;
    this.onSave = onSave;
    this.accentColor = accentColor;
    this.isDark = isDark;

    // Clear container
    this.container.innerHTML = '';
    this.container.style.display = 'flex';
    this.container.style.flexDirection = 'column';
    this.container.style.height = '100%';

    // Create Toolbar
    this.toolbar = document.createElement('div');
    this.toolbar.className = 'vanilla-prd-toolbar';
    this.setupToolbar();

    // Create Editor Area
    this.editor = document.createElement('div');
    this.editor.className = 'vanilla-prd-editor-content';
    this.setupEditor(initialContent);

    this.container.appendChild(this.toolbar);
    this.container.appendChild(this.editor);

    this.injectStyles();
    this.initEventListeners();
  }

  private injectStyles() {
    const styleId = 'vanilla-prd-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .prd-code-block {
        margin: 16px 0;
        border-radius: 6px;
        overflow: hidden;
        background-color: #0d1117;
        border: 1px solid #30363d;
      }
      .prd-code-header {
        background-color: #000000;
        color: #10b981;
        padding: 4px 12px;
        font-size: 11px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid #30363d;
      }
      .prd-code-block pre {
        margin: 0;
        padding: 16px;
        background: transparent;
      }
      .prd-code-block code {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-size: 13px;
        line-height: 1.5;
        tab-size: 4;
      }
    `;
    document.head.appendChild(style);
  }

  private setupToolbar() {
    Object.assign(this.toolbar.style, {
      display: 'flex',
      flexWrap: 'wrap',
      gap: '4px',
      padding: '8px',
      borderBottom: '1px solid #3f3f4620',
      backgroundColor: this.isDark ? '#18181b' : '#f4f4f5',
      position: 'sticky',
      top: '0',
      zIndex: '20',
    });

    const menus = [
      {
        label: 'Paragraph',
        items: [
          { label: 'Heading 1', icon: '⌘1', action: () => this.runCommand('formatBlock', 'h1') },
          { label: 'Heading 2', icon: '⌘2', action: () => this.runCommand('formatBlock', 'h2') },
          { label: 'Heading 3', icon: '⌘3', action: () => this.runCommand('formatBlock', 'h3') },
          { label: 'Heading 4', icon: '⌘4', action: () => this.runCommand('formatBlock', 'h4') },
          { label: 'Paragraph', icon: '⌘0', action: () => this.runCommand('formatBlock', 'p') },
          { type: 'separator' },
          { label: 'Quote', icon: '⌥⌘Q', action: () => this.runCommand('formatBlock', 'blockquote') },
          { label: 'Math Block', icon: '⌥⌘B', action: () => this.runCommand('insert-math-block') },
          { label: 'Table', icon: '', action: () => this.runCommand('insert-table') },
          { label: 'Horizontal Line', icon: '⌥⌘-', action: () => this.runCommand('insert-hr') },
          { label: 'YAML Front Matter', icon: '', action: () => this.runCommand('insert-yaml') },
        ]
      },
      {
        label: 'Code Block',
        items: [
          { label: 'Plain Text', action: () => this.runCommand('insert-code-fence', '') },
          { label: 'Python', action: () => this.runCommand('insert-code-fence', 'python') },
          { label: 'JavaScript', action: () => this.runCommand('insert-code-fence', 'javascript') },
          { label: 'TypeScript', action: () => this.runCommand('insert-code-fence', 'typescript') },
          { label: 'Rust', action: () => this.runCommand('insert-code-fence', 'rust') },
          { label: 'JSON', action: () => this.runCommand('insert-code-fence', 'json') },
          { label: 'YAML', action: () => this.runCommand('insert-code-fence', 'yaml') },
        ]
      },
      {
        label: 'Format',
        items: [
          { label: 'Strong', icon: '⌘B', action: () => this.runCommand('bold') },
          { label: 'Emphasis', icon: '⌘I', action: () => this.runCommand('italic') },
          { label: 'Underline', icon: '⌘U', action: () => this.runCommand('underline') },
          { label: 'Code', icon: '⌃`', action: () => this.runCommand('insert-code') },
          { type: 'separator' },
          { label: 'Hyperlink', icon: '⌘K', action: () => {
            const url = prompt('Enter URL:');
            if (url) this.runCommand('createLink', url);
          }},
          { label: 'Clear Format', icon: '⌘\\', action: () => this.runCommand('removeFormat') },
        ]
      },
      {
        label: 'Lists',
        items: [
          { label: 'Ordered List', icon: '⌥⌘O', action: () => this.runCommand('insertOrderedList') },
          { label: 'Unordered List', icon: '⌥⌘U', action: () => this.runCommand('insertUnorderedList') },
          { label: 'Task List', icon: '⌥⌘X', action: () => this.runCommand('insert-checklist') },
        ]
      }
    ];

    menus.forEach(menuInfo => {
      const menuContainer = document.createElement('div');
      menuContainer.className = 'vanilla-menu-dropdown';
      Object.assign(menuContainer.style, {
        position: 'relative',
        display: 'inline-block'
      });

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = menuInfo.label;
      Object.assign(btn.style, {
        padding: '4px 12px',
        fontSize: '12px',
        fontWeight: '500',
        borderRadius: '4px',
        border: 'none',
        backgroundColor: 'transparent',
        color: this.isDark ? '#e4e4e7' : '#27272a',
        cursor: 'pointer',
        transition: 'all 0.1s'
      });

      const dropdown = document.createElement('div');
      dropdown.className = 'vanilla-dropdown-content';
      Object.assign(dropdown.style, {
        display: 'none',
        position: 'absolute',
        top: '100%',
        left: '0',
        backgroundColor: this.isDark ? '#18181b' : '#ffffff',
        border: '1px solid #3f3f46',
        borderRadius: '6px',
        padding: '4px',
        minWidth: '180px',
        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
        zIndex: '100'
      });

      menuInfo.items.forEach((item: any) => {
        if (item.type === 'separator') {
          const hr = document.createElement('div');
          Object.assign(hr.style, {
            height: '1px',
            backgroundColor: '#3f3f4620',
            margin: '4px 0'
          });
          dropdown.appendChild(hr);
          return;
        }

        const itemBtn = document.createElement('button');
        itemBtn.type = 'button';
        itemBtn.innerHTML = `<span style="flex: 1; text-align: left;">${item.label}</span> <span style="font-size: 10px; opacity: 0.5; margin-left: 8px;">${item.icon || ''}</span>`;
        Object.assign(itemBtn.style, {
          background: 'none',
          border: 'none',
          color: this.isDark ? '#e4e4e7' : '#27272a',
          padding: '6px 10px',
          display: 'flex',
          alignItems: 'center',
          fontSize: '13px',
          cursor: 'pointer',
          borderRadius: '4px',
          width: '100%',
          transition: 'background 0.1s'
        });

        itemBtn.onmouseenter = () => itemBtn.style.backgroundColor = this.accentColor + '20';
        itemBtn.onmouseleave = () => itemBtn.style.backgroundColor = 'transparent';
        itemBtn.onmousedown = (e) => e.preventDefault();
        itemBtn.onclick = () => {
          item.action?.();
          dropdown.style.display = 'none';
        };
        dropdown.appendChild(itemBtn);
      });

      menuContainer.onmouseenter = () => {
        btn.style.backgroundColor = this.isDark ? '#27272a' : '#e4e4e7';
        dropdown.style.display = 'block';
      };
      
      menuContainer.onmouseleave = () => {
        btn.style.backgroundColor = 'transparent';
        dropdown.style.display = 'none';
      };

      menuContainer.appendChild(btn);
      menuContainer.appendChild(dropdown);
      this.toolbar.appendChild(menuContainer);
    });

    // Add a separator
    const sep = document.createElement('div');
    Object.assign(sep.style, { width: '1px', height: '20px', backgroundColor: '#3f3f4620', margin: '0 8px', alignSelf: 'center' });
    this.toolbar.appendChild(sep);

    // Keep some direct buttons
    const directButtons = [
      { label: 'B', title: 'Bold (Cmd+B)', action: () => this.runCommand('bold') },
      { label: 'I', title: 'Italic (Cmd+I)', action: () => this.runCommand('italic') },
      { label: 'Code', title: 'Inline Code (Ctrl+`)', action: () => this.runCommand('insert-code') },
      { label: 'List', title: 'Bullet List (Opt+Cmd+U)', action: () => this.runCommand('insertUnorderedList') },
      { label: 'Check', title: 'Task List (Opt+Cmd+X)', action: () => this.runCommand('insert-checklist') },
      { label: 'Box', title: 'Details Block', action: () => this.runCommand('insert-details') },
      { label: 'Msg', title: 'Comment', action: () => this.runCommand('insert-comment') },
      { label: '---', title: 'Horizontal Line (Opt+Cmd+-)', action: () => this.runCommand('insert-hr') },
      { label: 'Link', title: 'Hyperlink (Cmd+K)', action: () => {
        const url = prompt('Enter URL:');
        if (url) this.runCommand('createLink', url);
      }},
    ];

    directButtons.forEach(btnInfo => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = btnInfo.label;
      btn.title = btnInfo.title;
      Object.assign(btn.style, {
        padding: '4px 8px',
        fontSize: '11px',
        fontWeight: 'bold',
        borderRadius: '4px',
        border: '1px solid #3f3f4640',
        backgroundColor: 'transparent',
        color: this.isDark ? '#e4e4e7' : '#27272a',
        cursor: 'pointer',
        transition: 'all 0.2s'
      });

      btn.onmouseenter = () => btn.style.backgroundColor = this.accentColor + '20';
      btn.onmouseleave = () => btn.style.backgroundColor = 'transparent';
      btn.onmousedown = (e) => e.preventDefault();
      btn.onclick = () => btnInfo.action();
      
      this.toolbar.appendChild(btn);
    });
  }

  private setupEditor(content: string) {
    this.editor.contentEditable = 'true';
    this.editor.spellcheck = true;
    Object.assign(this.editor.style, {
      flex: '1',
      padding: '24px',
      outline: 'none',
      overflowY: 'auto',
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
      backgroundColor: 'transparent'
    });
    
    this.editor.innerHTML = this.markdownToHtml(content);
    this.checkSelectionMode();
  }

  private initEventListeners() {
    this.editor.addEventListener('focus', () => {
      this.isFocused = true;
    });

    document.addEventListener('selectionchange', () => {
      if (this.isFocused) this.checkSelectionMode();
    });

    this.editor.addEventListener('blur', (e) => {
      const relatedTarget = e.relatedTarget as HTMLElement;
      if (relatedTarget && (
          relatedTarget.closest('.vanilla-context-menu') || 
          relatedTarget.closest('.vanilla-prd-toolbar') ||
          relatedTarget.closest('input')
      )) {
        return;
      }

      this.isFocused = false;
      setTimeout(() => {
        if (!this.editor.contains(document.activeElement)) {
          this.onChange(this.getContent());
        }
      }, 100);
    });

    this.editor.addEventListener('input', (e) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains('prd-summary')) {
        const text = target.textContent?.trim();
        if (text === 'Metadata') {
          // Check if there are other summaries named Metadata
          const summaries = Array.from(this.editor.querySelectorAll('.prd-summary'));
          const otherMetadata = summaries.find(s => s !== target && s.textContent?.trim() === 'Metadata');
          if (otherMetadata) {
            // Revert or change to New Section
            target.textContent = 'New Section';
          }
        }
      }
      this.onChange(this.getContent());
    });

    this.editor.addEventListener('keydown', (e) => this.handleKeyDown(e));
    this.editor.addEventListener('paste', (e) => this.handlePaste(e));
    this.editor.addEventListener('contextmenu', (e) => this.handleContextMenu(e));
    
    document.addEventListener('mousedown', (e) => {
      if (this.contextMenu && !this.contextMenu.contains(e.target as Node)) {
        this.closeContextMenu();
      }
    });
  }

  public setContent(markdown: string) {
    if (this.isFocused) return;
    this.editor.innerHTML = this.markdownToHtml(markdown);
  }

  public getContent(): string {
    return this.htmlToMarkdown(this.editor.innerHTML);
  }

  public getIsFocused(): boolean {
    return this.isFocused;
  }

  private handleKeyDown(e: KeyboardEvent) {
    const selection = window.getSelection();
    const range = selection?.rangeCount ? selection.getRangeAt(0) : null;
    const node = range?.startContainer;
    const summary = node ? this.getClosestElementByClass(node, 'prd-summary') : null;

    if (summary) {
      const isMetadata = summary.textContent?.trim() === 'Metadata';
      
      // If it's Metadata, prevent any changes
      if (isMetadata) {
        const allowedKeys = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'PageUp', 'PageDown', 'Control', 'Command', 'Alt', 'Shift'];
        if (!allowedKeys.includes(e.key) && !e.metaKey && !e.ctrlKey) {
          e.preventDefault();
          return;
        }
      }

      // If Enter is pressed in summary, prevent it
      if (e.key === 'Enter') {
        e.preventDefault();
        return;
      }
    }

    if (e.metaKey || e.ctrlKey) {
      if (e.altKey) {
        // Opt+Cmd shortcuts
        switch (e.key.toLowerCase()) {
          case 'b': e.preventDefault(); this.runCommand('insert-math-block'); break;
          case 'c': e.preventDefault(); this.runCommand('insert-code-fence'); break;
          case 'q': e.preventDefault(); this.runCommand('formatBlock', 'blockquote'); break;
          case 'o': e.preventDefault(); this.runCommand('insertOrderedList'); break;
          case 'u': e.preventDefault(); this.runCommand('insertUnorderedList'); break;
          case 'x': e.preventDefault(); this.runCommand('insert-checklist'); break;
          case 'l': e.preventDefault(); this.runCommand('insert-details'); break;
          case '-': e.preventDefault(); this.runCommand('insert-hr'); break;
        }
      } else {
        // Cmd shortcuts
        switch (e.key) {
          case 'b': e.preventDefault(); this.runCommand('bold'); break;
          case 'i': e.preventDefault(); this.runCommand('italic'); break;
          case 'u': e.preventDefault(); this.runCommand('underline'); break;
          case 'k':
            e.preventDefault();
            const url = prompt('Enter URL:');
            if (url) this.runCommand('createLink', url);
            break;
          case 's':
            e.preventDefault();
            if (this.onSave) {
              this.onSave();
            } else {
              this.onChange(this.getContent());
            }
            break;
          case '1': e.preventDefault(); this.runCommand('formatBlock', 'h1'); break;
          case '2': e.preventDefault(); this.runCommand('formatBlock', 'h2'); break;
          case '3': e.preventDefault(); this.runCommand('formatBlock', 'h3'); break;
          case '4': e.preventDefault(); this.runCommand('formatBlock', 'h4'); break;
          case '5': e.preventDefault(); this.runCommand('formatBlock', 'h5'); break;
          case '6': e.preventDefault(); this.runCommand('formatBlock', 'h6'); break;
          case '0': e.preventDefault(); this.runCommand('formatBlock', 'p'); break;
          case '\\': e.preventDefault(); this.runCommand('removeFormat'); break;
        }
      }
    }

    if (e.key === '`') {
      if (e.ctrlKey) {
        e.preventDefault();
        this.runCommand('insert-code');
      }
    }

    if (e.key === 'Tab') {
      e.preventDefault();
      this.execCommand('insertText', '    ');
    }

    if (e.key === 'Enter') {
      this.handleEnter(e);
    }
  }

  private handleEnter(e: KeyboardEvent) {
    const selection = window.getSelection();
    if (!selection?.rangeCount) return;

    const range = selection.getRangeAt(0);
    const node = range.startContainer;
    const listItem = this.getClosestListItem(node);

    if (listItem) {
      const content = listItem.textContent?.trim() || '';
      if (content === '') {
        e.preventDefault();
        this.execCommand('outdent');
        const div = document.createElement('div');
        div.innerHTML = '<br>';
        listItem.parentElement?.insertBefore(div, listItem.nextSibling);
        listItem.remove();
        
        const newRange = document.createRange();
        newRange.setStart(div, 0);
        newRange.collapse(true);
        selection.removeAllRanges();
        selection.addRange(newRange);
      }
    }
  }

  private getClosestListItem(node: Node): HTMLElement | null {
    let curr: Node | null = node;
    while (curr && curr !== this.editor) {
      if (curr.nodeType === Node.ELEMENT_NODE && (curr as HTMLElement).tagName.toLowerCase() === 'li') {
        return curr as HTMLElement;
      }
      curr = curr.parentNode;
    }
    return null;
  }

  private handlePaste(e: ClipboardEvent) {
    e.preventDefault();
    const html = e.clipboardData?.getData('text/html');
    const text = e.clipboardData?.getData('text/plain');

    if (html) {
      const md = this.htmlToMarkdown(html);
      this.runCommand('insertHTML', this.markdownToHtml(md));
    } else if (text) {
      if (text.includes('#') || text.includes('- ') || text.includes('**')) {
        this.runCommand('insertHTML', this.markdownToHtml(text));
      } else {
        this.execCommand('insertText', text);
      }
    }
  }

  public runCommand(command: string, value: any = undefined) {
    this.editor.focus();

    switch (command) {
      case 'insert-details':
        this.execCommand('insertHTML', '<div class="prd-details-container"><div class="prd-summary" contenteditable="true">New Section</div><div class="prd-details-content"><div><br></div></div></div>');
        break;
      case 'insert-comment':
        this.execCommand('insertHTML', '<div class="prd-comment" data-comment="Comment">&lt;!-- Comment --&gt;</div>');
        break;
      case 'insert-checklist':
        this.execCommand('insertHTML', '<li class="prd-checklist-item" data-checked="false"><input type="checkbox"> New task</li>');
        break;
      case 'insert-hr':
        this.execCommand('insertHTML', '<hr>');
        break;
      case 'insert-code-fence':
        const lang = value || '';
        this.execCommand('insertHTML', `<div class="prd-code-block" data-lang="${lang}" contenteditable="false"><div class="prd-code-header">${lang || 'plaintext'}</div><pre contenteditable="true"><code>\n\n</code></pre></div>`);
        break;
      case 'insert-math-block':
        this.execCommand('insertHTML', '<div class="prd-math-block">$$\n\n$$</div>');
        break;
      case 'insert-yaml':
        this.execCommand('insertHTML', '<div class="prd-yaml">---\n\n---</div>');
        break;
      case 'insert-table':
        this.execCommand('insertHTML', '<table border="1"><thead><tr><th>Header</th><th>Header</th></tr></thead><tbody><tr><td>Data</td><td>Data</td></tr></tbody></table>');
        break;
      case 'insert-code':
        this.execCommand('insertHTML', '<code>code</code>');
        break;
      default:
        this.execCommand(command, value);
    }
  }

  private execCommand(command: string, value: string | undefined = undefined) {
    document.execCommand(command, false, value);
  }

  private checkSelectionMode() {
    const selection = window.getSelection();
    if (!selection?.rangeCount) return;

    const node = selection.getRangeAt(0).startContainer;
    const summary = this.getClosestElementByClass(node, 'prd-summary');
    const details = this.getClosestElementByClass(node, 'prd-details-container');

    if (summary) {
      this.setEditorMode('summary');
    } else if (details) {
      this.setEditorMode('details');
    } else {
      this.setEditorMode('normal');
    }
  }

  private setEditorMode(mode: 'normal' | 'summary' | 'details') {
    const isSummary = mode === 'summary';
    const isDetails = mode === 'details';

    // Update toolbar appearance
    const dropdownContainers = this.toolbar.querySelectorAll('.vanilla-menu-dropdown');
    const directButtons = Array.from(this.toolbar.querySelectorAll('button')).filter(btn => !btn.closest('.vanilla-dropdown-content'));

    dropdownContainers.forEach(container => {
      const c = container as HTMLElement;
      c.style.opacity = isSummary ? '0.3' : '1';
      c.style.pointerEvents = isSummary ? 'none' : 'auto';
    });

    directButtons.forEach(btn => {
      // If it's a dropdown trigger button, it's already handled by the container
      if (btn.closest('.vanilla-menu-dropdown')) return;
      
      const b = btn as HTMLElement;
      b.style.opacity = isSummary ? '0.3' : '1';
      b.style.pointerEvents = isSummary ? 'none' : 'auto';
    });

    // Special indicator for mode
    this.toolbar.style.borderTop = isSummary ? `2px solid ${this.accentColor}` : isDetails ? `2px solid ${this.accentColor}40` : 'none';
  }

  private getClosestElementByClass(node: Node, className: string): HTMLElement | null {
    let curr: Node | null = node;
    while (curr && curr !== this.editor) {
      if (curr.nodeType === Node.ELEMENT_NODE && (curr as HTMLElement).classList.contains(className)) {
        return curr as HTMLElement;
      }
      curr = curr.parentNode;
    }
    return null;
  }

  private markdownToHtml(md: string): string {
    if (!md) return '';

    // Convert markdown to HTML for editing
    let html = md
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      // Comments
      .replace(/^&lt;!--\s*(.*?)\s*--&gt;$/gm, '<div class="prd-comment" data-comment="$1">&lt;!-- $1 --&gt;</div>')
      // Details/Summary block
      .replace(/^&lt;details&gt;\n&lt;summary&gt;(.*?)&lt;\/summary&gt;\n([\s\S]*?)\n&lt;\/details&gt;$/gm, 
        '<div class="prd-details-container"><div class="prd-summary" contenteditable="true">$1</div><div class="prd-details-content">$2</div></div>')
      // Fallback for partial tags
      .replace(/^&lt;details&gt;$/gm, '<div class="prd-details-open">&lt;details&gt;</div>')
      .replace(/^&lt;\/details&gt;$/gm, '<div class="prd-details-close">&lt;/details&gt;</div>')
      .replace(/^&lt;summary&gt;(.*?)&lt;\/summary&gt;$/gm, '<div class="prd-summary" contenteditable="true">$1</div>')
      // Math blocks
      .replace(/^\$\$\n([\s\S]*?)\n\$\$$/gm, '<div class="prd-math-block">$$\n$1\n$$</div>')
      // YAML Front Matter
      .replace(/^---\n([\s\S]*?)\n---$/gm, '<div class="prd-yaml">---\n$1\n---</div>')
      // Headers
      .replace(/^# (.*$)/gm, '<h1>$1</h1>')
      .replace(/^## (.*$)/gm, '<h2>$1</h2>')
      .replace(/^### (.*$)/gm, '<h3>$1</h3>')
      .replace(/^#### (.*$)/gm, '<h4>$1</h4>')
      // Checklist
      .replace(/^- \[ \](.*$)/gm, '<li class="prd-checklist-item" data-checked="false"><input type="checkbox"> $1</li>')
      .replace(/^- \[x\](.*$)/gm, '<li class="prd-checklist-item" data-checked="true"><input type="checkbox" checked> $1</li>')
      // Lists
      .replace(/^- (?!\[ \]|\[x\])(.*$)/gm, '<li>$1</li>')
      // HR
      .replace(/^---$/gm, '<hr>')
      // Quotes
      .replace(/^> (.*$)/gm, '<blockquote>$1</blockquote>')
      // Code blocks
      .replace(/```(.*?)\n([\s\S]*?)```/g, (match, lang, content) => {
        const language = lang.trim() || 'plaintext';
        let highlighted = content;
        try {
          if (language && hljs.getLanguage(language)) {
            highlighted = hljs.highlight(content, { language }).value;
          } else {
            highlighted = hljs.highlightAuto(content).value;
          }
        } catch (e) {
          console.error('Highlighting error:', e);
        }
        return `<div class="prd-code-block" data-lang="${language}" contenteditable="false"><div class="prd-code-header">${language}</div><pre contenteditable="true"><code>${highlighted}</code></pre></div>`;
      })
      .replace(/```([\s\S]*?)```/g, (match, content) => {
        let highlighted = content;
        try {
          highlighted = hljs.highlightAuto(content).value;
        } catch (e) {}
        return `<div class="prd-code-block" data-lang="plaintext" contenteditable="false"><div class="prd-code-header">plaintext</div><pre contenteditable="true"><code>${highlighted}</code></pre></div>`;
      })
      // Bold
      .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
      // Italic
      .replace(/_(.*?)_/g, '<i>$1</i>')
      // Strikethrough
      .replace(/~~(.*?)~~/g, '<strike>$1</strike>')
      // Inline code
      .replace(/`(.*?)`/g, '<code>$1</code>')
      // Links
      .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2">$1</a>');

    // Wrap lines in divs if not already wrapped
    return html.split('\n').map(line => {
      if (line.trim() === '') return '<div><br></div>';
      if (line.startsWith('<h') || 
          line.startsWith('<li') || 
          line.startsWith('<pre') || 
          line.startsWith('<div') || 
          line.startsWith('<blockquote') ||
          line.startsWith('<hr')) return line;
      return `<div>${line}</div>`;
    }).join('');
  }

  private htmlToMarkdown(html: string): string {
    const temp = document.createElement('div');
    temp.innerHTML = html;

    const processNode = (node: Node): string => {
      if (node.nodeType === Node.TEXT_NODE) {
        return node.textContent || '';
      }

      if (node.nodeType === Node.ELEMENT_NODE) {
        const el = node as HTMLElement;
        const tag = el.tagName.toLowerCase();
        
        const children = Array.from(el.childNodes).map(processNode).join('');

        // Handle special divs
        if (tag === 'div') {
          if (el.classList.contains('prd-comment')) return `<!-- ${el.dataset.comment} -->\n`;
          if (el.classList.contains('prd-code-block')) {
            const lang = el.dataset.lang || '';
            const code = el.querySelector('code')?.textContent || '';
            return `\n\`\`\`${lang}\n${code}\n\`\`\`\n`;
          }
          if (el.classList.contains('prd-details-container')) {
            const summary = el.querySelector('.prd-summary')?.textContent || 'Metadata';
            return `<details>\n<summary>${summary}</summary>\n${children}\n</details>\n`;
          }
          if (el.classList.contains('prd-details-open')) return `<details>\n`;
          if (el.classList.contains('prd-details-close')) return `</details>\n`;
          if (el.classList.contains('prd-summary')) return `<summary>${el.textContent}</summary>\n`;
          if (el.classList.contains('prd-math-block')) return `${children}\n`;
          if (el.classList.contains('prd-yaml')) return `${children}\n`;
        }

        switch (tag) {
          case 'h1': return `# ${children}\n`;
          case 'h2': return `## ${children}\n`;
          case 'h3': return `### ${children}\n`;
          case 'h4': return `#### ${children}\n`;
          case 'h5': return `##### ${children}\n`;
          case 'h6': return `###### ${children}\n`;
          case 'p': return `${children}\n`;
          case 'u': return `<u>${children}</u>`;
          case 'b':
          case 'strong': return `**${children}**`;
          case 'i':
          case 'em': return `_${children}_`;
          case 'strike': return `~~${children}~~`;
          case 'a': return `[${children}](${el.getAttribute('href')})`;
          case 'li':
            if (el.classList.contains('prd-checklist-item')) {
              const checked = el.querySelector('input')?.checked;
              return `- [${checked ? 'x' : ' '}]${children.replace(/.*<\/input>\s?/, '')}\n`;
            }
            return `- ${children}\n`;
          case 'blockquote': return `> ${children}\n`;
          case 'pre': 
            const codeEl = el.querySelector('code');
            return codeEl ? codeEl.textContent || '' : el.textContent || '';
          case 'code': 
            if (el.parentElement?.tagName.toLowerCase() === 'pre') {
              return el.textContent || '';
            }
            return `\`${children}\``;
          case 'hr': return `---\n`;
          case 'table': return `\n${this.htmlTableToMarkdown(el)}\n`;
          case 'br': return '';
          case 'div': return `${children}\n`;
          default: return children;
        }
      }
      return '';
    };

    return Array.from(temp.childNodes)
      .map(processNode)
      .join('')
      .replace(/\n\s*\n\s*\n/g, '\n\n') // Fix excessive newlines
      .trim();
  }

  private htmlTableToMarkdown(table: HTMLElement): string {
    const rows = Array.from(table.querySelectorAll('tr'));
    if (rows.length === 0) return '';

    const mdRows = rows.map(row => {
      const cells = Array.from(row.querySelectorAll('th, td'));
      return `| ${cells.map(cell => cell.textContent?.trim() || '').join(' | ')} |`;
    });

    const headerCount = rows[0].querySelectorAll('th, td').length;
    const divider = `| ${Array(headerCount).fill('---').join(' | ')} |`;
    
    mdRows.splice(1, 0, divider);
    return mdRows.join('\n');
  }

  private handleContextMenu(e: MouseEvent) {
    e.preventDefault();
    this.closeContextMenu();

    const target = e.target as HTMLElement;
    const isInsideDetails = !!target.closest('.prd-details-container');
    const isSummary = !!target.closest('.prd-summary');

    const menu = document.createElement('div');
    this.contextMenu = menu;
    menu.className = 'vanilla-context-menu';
    
    // Styling the menu
    Object.assign(menu.style, {
      position: 'fixed',
      top: `${e.clientY}px`,
      left: `${e.clientX}px`,
      backgroundColor: this.isDark ? '#18181b' : '#ffffff',
      border: '1px solid #3f3f46',
      borderRadius: '8px',
      padding: '4px',
      boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
      zIndex: '1000',
      minWidth: '160px',
      display: 'flex',
      flexDirection: 'column',
      gap: '2px'
    });

    let items: any[] = [];

    if (isInsideDetails) {
      items = [
        { label: 'Remove Details Block', icon: '🗑️', action: (e: MouseEvent) => { 
          e.stopPropagation(); 
          const container = target.closest('.prd-details-container');
          if (container) {
            const content = container.querySelector('.prd-details-content')?.innerHTML || '';
            container.outerHTML = content;
          }
        }},
        { label: 'Clear Summary', icon: 'Tx', action: (e: MouseEvent) => {
          e.stopPropagation();
          const summary = target.closest('.prd-details-container')?.querySelector('.prd-summary');
          if (summary) summary.textContent = 'Metadata';
        }}
      ];
    } else {
      items = [
        { label: 'Bold', icon: '⌘B', action: (e: MouseEvent) => { e.stopPropagation(); this.execCommand('bold'); } },
        { label: 'Italic', icon: '⌘I', action: (e: MouseEvent) => { e.stopPropagation(); this.execCommand('italic'); } },
        { label: 'Link', icon: '⌘K', action: (e: MouseEvent) => {
          e.stopPropagation();
          const url = prompt('Enter URL:');
          if (url) this.execCommand('createLink', url);
        }},
        { label: 'Clear Format', icon: '⌘\\', action: (e: MouseEvent) => { e.stopPropagation(); this.execCommand('removeFormat'); } },
      ];
    }

    items.forEach(item => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.innerHTML = `<span style="flex: 1; text-align: left;">${item.label}</span> <span style="font-size: 10px; opacity: 0.5;">${item.icon || ''}</span>`;
      Object.assign(btn.style, {
        background: 'none',
        border: 'none',
        color: this.isDark ? '#e4e4e7' : '#27272a',
        padding: '6px 12px',
        display: 'flex',
        alignItems: 'center',
        fontSize: '13px',
        cursor: 'pointer',
        borderRadius: '4px',
        width: '100%',
        transition: 'background 0.1s'
      });
      
      btn.onmouseenter = () => btn.style.backgroundColor = this.accentColor + '20';
      btn.onmouseleave = () => btn.style.backgroundColor = 'transparent';
      btn.onmousedown = (e) => {
        e.preventDefault(); // Prevent blur of editor
      };
      btn.onclick = (e) => {
        item.action(e);
        this.closeContextMenu();
      };
      menu.appendChild(btn);
    });

    document.body.appendChild(menu);
  }

  private closeContextMenu() {
    if (this.contextMenu) {
      this.contextMenu.remove();
      this.contextMenu = null;
    }
  }

  public destroy() {
    this.closeContextMenu();
    // Remove other global listeners if any
  }
}
