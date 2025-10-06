# MMO Simulator Documentation

This directory contains the Sphinx-based documentation for MMO Simulator.

## Building Documentation Locally

### Prerequisites

Install documentation dependencies:

```bash
pip install -r requirements.txt
```

### Build HTML Documentation

```bash
cd docs
make html
```

The generated HTML will be in `docs/build/html/`. Open `docs/build/html/index.html` in your browser.

### Clean Build

To remove previous builds:

```bash
make clean
```

## Documentation Structure

- `source/` - RST source files
  - `getting-started/` - Installation, quickstart, basic concepts
  - `user-guide/` - Configuration, agents, world, running sims
  - `api/` - Auto-generated API reference
  - `architecture/` - Design philosophy, simulation loop, database
  - `tutorials/` - Custom agents, actions, analysis
  - `examples/` - Example scripts and walkthroughs
  - `_static/` - Custom CSS and images
  - `_templates/` - Custom Sphinx templates

## Deployment

Documentation is automatically deployed via GitHub Actions:

1. **GitHub Pages**: https://aoifehughes.github.io/MMO_Simulator/ (gh-pages branch)
2. **Blog Integration**: https://aoifehughes.github.io/mmo-simulator/

Deployment triggers on:
- Push to `main` branch with changes to `docs/` or Python source
- Manual workflow dispatch

## Writing Documentation

### RST Syntax

Basic formatting:

```rst
Section Header
==============

Subsection
----------

**Bold**, *italic*, ``code``

.. code-block:: python

   # Python code example
   print("Hello")

.. note::
   Important note

.. warning::
   Warning message
```

### Adding New Pages

1. Create `.rst` file in appropriate directory
2. Add to `index.rst` toctree:

```rst
.. toctree::
   :maxdepth: 2

   new-section/new-page
```

3. Rebuild docs

### API Documentation

API docs are auto-generated from Python docstrings using Sphinx autodoc. Write docstrings in Google or NumPy style:

```python
def my_function(param1: str, param2: int) -> bool:
    """Short description.

    Longer description if needed.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Example:
        >>> my_function("test", 42)
        True
    """
    return True
```

## Troubleshooting

### Module import errors

Ensure the project root is in Python path. This is handled in `conf.py`:

```python
sys.path.insert(0, os.path.abspath('../../'))
```

### Missing dependencies

```bash
pip install -r requirements.txt -r ../requirements.txt
```

### Build warnings

Check `docs/build/html/.buildinfo` for details. Fix any broken references or malformed RST.

## Resources

- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [RST Primer](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html)
- [ReadTheDocs Theme](https://sphinx-rtd-theme.readthedocs.io/)
