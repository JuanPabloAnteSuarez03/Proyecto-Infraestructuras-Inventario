#!/usr/bin/env python3
"""
Generador de documentación HTML desde archivos Markdown.
Convierte la documentación .md a HTML con estilos visuales modernos.
"""

import os
import re
from pathlib import Path

# Template HTML base
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Sistema de Inventario</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        {css}
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <a href="../index.html" class="nav-brand">📚 Documentación Inventario</a>
            <div class="nav-links">
                <a href="../index.html">🏠 Inicio</a>
                <a href="00_indice.html">📑 Índice</a>
                <a href="https://github.com" target="_blank">💻 GitHub</a>
            </div>
        </div>
    </nav>

    <div class="container">
        <aside class="sidebar">
            <h3>📖 Navegación</h3>
            <ul class="sidebar-menu">
                <li><a href="00_indice.html">🗺️ Índice</a></li>
                <li><a href="01_arquitectura.html">🏗️ Arquitectura</a></li>
                <li><a href="02_sistema_colas.html">🔄 Sistema de Colas</a></li>
                <li><a href="03_paralelismo.html">⚡ Paralelismo</a></li>
                <li><a href="04_flujos.html">📊 Flujos</a></li>
                <li><a href="05_guia_desarrollo.html">🛠️ Desarrollo</a></li>
                <li><a href="readme.html">📖 README</a></li>
                <li><a href="testing.html">🧪 Testing</a></li>
            </ul>
        </aside>

        <main class="content">
            {content}
        </main>
    </div>

    <footer class="footer">
        <p>Desarrollado con ❤️ usando FastAPI, Redis, RQ y PostgreSQL</p>
        <p><a href="../index.html">← Volver al índice</a></p>
    </footer>

    <script>
        hljs.highlightAll();
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    </script>
</body>
</html>
"""

CSS_STYLES = """
:root {
    --primary: #6366f1;
    --primary-dark: #4f46e5;
    --secondary: #8b5cf6;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --dark: #1e293b;
    --gray: #64748b;
    --light: #f1f5f9;
    --white: #ffffff;
    --border: #e2e8f0;
    --code-bg: #282c34;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Inter', sans-serif;
    background: var(--light);
    color: var(--dark);
    line-height: 1.7;
}

.navbar {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    position: sticky;
    top: 0;
    z-index: 1000;
}

.nav-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 16px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.nav-brand {
    color: var(--white);
    font-size: 1.25rem;
    font-weight: 600;
    text-decoration: none;
}

.nav-links {
    display: flex;
    gap: 24px;
}

.nav-links a {
    color: rgba(255, 255, 255, 0.9);
    text-decoration: none;
    font-weight: 500;
    transition: color 0.3s;
}

.nav-links a:hover {
    color: var(--white);
}

.container {
    max-width: 1400px;
    margin: 40px auto;
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 40px;
    padding: 0 24px;
}

.sidebar {
    background: var(--white);
    border-radius: 12px;
    padding: 24px;
    height: fit-content;
    position: sticky;
    top: 100px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
}

.sidebar h3 {
    color: var(--dark);
    font-size: 1.1rem;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 2px solid var(--primary);
}

.sidebar-menu {
    list-style: none;
}

.sidebar-menu li {
    margin-bottom: 8px;
}

.sidebar-menu a {
    display: block;
    padding: 10px 12px;
    color: var(--gray);
    text-decoration: none;
    border-radius: 8px;
    transition: all 0.3s;
    font-size: 0.95rem;
}

.sidebar-menu a:hover {
    background: var(--primary);
    color: var(--white);
    transform: translateX(4px);
}

.content {
    background: var(--white);
    border-radius: 12px;
    padding: 40px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    min-height: 600px;
}

.content h1 {
    color: var(--dark);
    font-size: 2.5rem;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 3px solid var(--primary);
}

.content h2 {
    color: var(--dark);
    font-size: 2rem;
    margin-top: 40px;
    margin-bottom: 20px;
    padding-left: 12px;
    border-left: 4px solid var(--primary);
}

.content h3 {
    color: var(--dark);
    font-size: 1.5rem;
    margin-top: 32px;
    margin-bottom: 16px;
}

.content p {
    margin-bottom: 16px;
    color: var(--gray);
}

.content ul, .content ol {
    margin: 16px 0 16px 24px;
    color: var(--gray);
}

.content li {
    margin-bottom: 8px;
}

.content a {
    color: var(--primary);
    text-decoration: none;
    font-weight: 500;
}

.content a:hover {
    text-decoration: underline;
}

.content code {
    font-family: 'Fira Code', monospace;
    background: var(--light);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.9em;
    color: var(--danger);
}

.content pre {
    background: var(--code-bg);
    border-radius: 8px;
    padding: 20px;
    overflow-x: auto;
    margin: 20px 0;
}

.content pre code {
    background: none;
    color: #abb2bf;
    padding: 0;
}

.content table {
    width: 100%;
    border-collapse: collapse;
    margin: 24px 0;
}

.content th {
    background: var(--primary);
    color: var(--white);
    padding: 12px;
    text-align: left;
    font-weight: 600;
}

.content td {
    padding: 12px;
    border-bottom: 1px solid var(--border);
}

.content tr:hover {
    background: var(--light);
}

.content blockquote {
    border-left: 4px solid var(--primary);
    padding: 16px 20px;
    margin: 20px 0;
    background: var(--light);
    border-radius: 0 8px 8px 0;
}

.footer {
    text-align: center;
    padding: 40px 24px;
    color: var(--gray);
}

.footer a {
    color: var(--primary);
    text-decoration: none;
    font-weight: 500;
}

@media (max-width: 1024px) {
    .container {
        grid-template-columns: 1fr;
    }

    .sidebar {
        position: relative;
        top: 0;
    }
}
"""

def simple_md_to_html(md_content):
    """Convierte Markdown a HTML de forma simple."""
    html = md_content
    
    # Encabezados
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    
    # Bloques de código
    html = re.sub(r'```(\w+)?\n(.*?)\n```', r'<pre><code class="language-\1">\2</code></pre>', html, flags=re.DOTALL)
    
    # Código inline
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    
    # Enlaces
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
    
    # Negritas
    html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
    
    # Cursivas
    html = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', html)
    
    # Listas
    html = re.sub(r'^\- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.*</li>\n)+', r'<ul>\n\g<0></ul>\n', html)
    
    # Párrafos
    lines = html.split('\n')
    in_list = False
    in_code = False
    new_lines = []
    
    for line in lines:
        if '<pre>' in line:
            in_code = True
        elif '</pre>' in line:
            in_code = False
        elif '<ul>' in line or '<ol>' in line:
            in_list = True
        elif '</ul>' in line or '</ol>' in line:
            in_list = False
        elif not in_code and not in_list and line.strip() and not line.startswith('<'):
            line = f'<p>{line}</p>'
        new_lines.append(line)
    
    html = '\n'.join(new_lines)
    
    # Blockquotes
    html = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
    
    return html

def convert_md_to_html(md_file, html_file):
    """Convierte un archivo Markdown a HTML."""
    print(f"Convirtiendo {md_file} → {html_file}")
    
    # Leer contenido
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Obtener título del primer # 
    title_match = re.search(r'^# (.+)$', md_content, re.MULTILINE)
    title = title_match.group(1) if title_match else "Documentación"
    
    # Convertir a HTML
    html_content = simple_md_to_html(md_content)
    
    # Generar HTML completo
    full_html = HTML_TEMPLATE.format(
        title=title,
        css=CSS_STYLES,
        content=html_content
    )
    
    # Guardar
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(full_html)
    
    print(f"✓ Creado: {html_file}")

def main():
    """Genera todos los archivos HTML."""
    docs_dir = Path(__file__).parent
    html_dir = docs_dir / 'html'
    html_dir.mkdir(exist_ok=True)
    
    # Mapeo de archivos
    files = {
        '00_INDICE.md': 'html/00_indice.html',
        '01_ARQUITECTURA_GENERAL.md': 'html/01_arquitectura.html',
        '02_SISTEMA_COLAS.md': 'html/02_sistema_colas.html',
        '03_PARALELISMO_CONCURRENCIA.md': 'html/03_paralelismo.html',
        '04_FLUJOS_INVENTARIO.md': 'html/04_flujos.html',
        '05_GUIA_DESARROLLO.md': 'html/05_guia_desarrollo.html',
        'README.md': 'html/readme.html',
        'TESTING.md': 'html/testing.html',
    }
    
    for md_file, html_file in files.items():
        md_path = docs_dir / md_file
        html_path = docs_dir / html_file
        
        if md_path.exists():
            convert_md_to_html(md_path, html_path)
        else:
            print(f"⚠️  No encontrado: {md_file}")
    
    print("\n✨ ¡Conversión completada!")
    print(f"📁 Archivos HTML generados en: {html_dir}")

if __name__ == '__main__':
    main()
