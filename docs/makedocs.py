#!/usr/bin/env python
"""
Script for building and customizing Kunqalay documentation.
This script can be used instead of make command to build the documentation.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Configuration
SOURCE_DIR = 'source'
BUILD_DIR = 'build'
HTML_DIR = os.path.join(BUILD_DIR, 'html')
DOCTREE_DIR = os.path.join(BUILD_DIR, 'doctrees')

def ensure_directory(path):
    """Ensure that a directory exists."""
    os.makedirs(path, exist_ok=True)

def build_html():
    """Build HTML documentation."""
    print("Building HTML documentation...")
    ensure_directory(HTML_DIR)
    ensure_directory(DOCTREE_DIR)
    
    try:
        subprocess.run([
            sys.executable, '-m', 'sphinx',
            '-b', 'html',
            '-d', DOCTREE_DIR,
            SOURCE_DIR,
            HTML_DIR
        ], check=True)
        print(f"HTML documentation built successfully in {HTML_DIR}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error building HTML documentation: {e}")
        return False

def build_pdf():
    """Build PDF documentation using LaTeX."""
    print("Building PDF documentation...")
    latex_dir = os.path.join(BUILD_DIR, 'latex')
    ensure_directory(latex_dir)
    ensure_directory(DOCTREE_DIR)
    
    try:
        # Build LaTeX files
        subprocess.run([
            sys.executable, '-m', 'sphinx',
            '-b', 'latex',
            '-d', DOCTREE_DIR,
            SOURCE_DIR,
            latex_dir
        ], check=True)
        
        # Run make in the latex directory
        current_dir = os.getcwd()
        os.chdir(latex_dir)
        
        if os.name == 'nt':  # Windows
            make_result = subprocess.run(['make.bat'], check=True)
        else:  # Unix-like
            make_result = subprocess.run(['make'], check=True)
        
        os.chdir(current_dir)
        
        print(f"PDF documentation built successfully in {latex_dir}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error building PDF documentation: {e}")
        if os.getcwd() != current_dir:
            os.chdir(current_dir)
        return False

def copy_static_files():
    """Copy additional static files."""
    print("Copying additional static files...")
    
    # Copy additional CSS files
    css_src = os.path.join(SOURCE_DIR, '_static', 'custom.css')
    css_dest = os.path.join(HTML_DIR, '_static', 'custom.css')
    
    if os.path.exists(css_src):
        ensure_directory(os.path.dirname(css_dest))
        shutil.copy2(css_src, css_dest)
    
    # You can add more static files to copy here
    
    print("Static files copied successfully.")

def create_images_dir():
    """Create images directory if it doesn't exist."""
    images_dir = os.path.join(SOURCE_DIR, '_static', 'images')
    ensure_directory(images_dir)
    print(f"Images directory created at {images_dir}")

def main():
    """Main function."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'html':
            success = build_html()
            if success:
                copy_static_files()
        elif command == 'pdf':
            build_pdf()
        elif command == 'images':
            create_images_dir()
        elif command == 'all':
            html_success = build_html()
            if html_success:
                copy_static_files()
            build_pdf()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: html, pdf, images, all")
    else:
        # Default to building HTML
        success = build_html()
        if success:
            copy_static_files()

if __name__ == '__main__':
    main() 