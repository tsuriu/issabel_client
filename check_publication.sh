#!/bin/bash

# Exit on error
set -e

echo "📦 Building package..."
python3 -m build

echo "🔍 Verifying package with twine check..."
python3 -m twine check dist/*

echo "✅ Package is ready for publication!"
