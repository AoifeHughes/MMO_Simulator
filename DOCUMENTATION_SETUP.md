# Documentation Setup Guide

Complete documentation for MMO Simulator has been created with Sphinx and ReadTheDocs theme. This guide covers deployment setup.

## 📚 What Was Created

### Documentation Structure

```
docs/
├── source/
│   ├── index.rst                      # Main documentation page
│   ├── getting-started/               # Installation, quickstart, concepts
│   ├── user-guide/                    # Configuration, agents, world, sims
│   ├── api/                           # Auto-generated API reference
│   ├── architecture/                  # Design philosophy, sim loop, DB schema
│   ├── tutorials/                     # Custom agents, actions, analysis
│   ├── examples/                      # Basic and complex simulation guides
│   ├── _static/custom.css             # Custom styling
│   └── conf.py                        # Sphinx configuration
├── Makefile                           # Build commands (Unix)
├── make.bat                           # Build commands (Windows)
└── requirements.txt                   # Doc dependencies
```

### GitHub Actions Workflow

`.github/workflows/docs.yml` - Automated CI/CD pipeline that:

1. **Builds** documentation on every push to `main` (when docs/ or Python files change)
2. **Deploys** to two locations:
   - **gh-pages branch** of this repository
   - **Your Hugo blog** at `static/mmo-simulator/`

## 🔧 Setup Steps

### 1. Install Documentation Dependencies (Local Testing)

```bash
cd /Users/aoife/git/MMO_Simulator
pip install -r docs/requirements.txt
```

### 2. Test Documentation Build Locally

```bash
cd docs
make html
```

Then open `docs/build/html/index.html` in your browser.

### 3. Configure GitHub Secret for Blog Deployment

The GitHub Actions workflow needs a Personal Access Token (PAT) to push to your blog repository.

#### Create Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → [Tokens (classic)](https://github.com/settings/tokens)
2. Click "Generate new token" → "Generate new token (classic)"
3. Configure the token:
   - **Note**: `MMO Simulator Docs Deployment`
   - **Expiration**: 90 days (or longer)
   - **Scopes**: Check `repo` (Full control of private repositories)
4. Click "Generate token"
5. **Copy the token** (you won't see it again!)

#### Add Token as Repository Secret

1. Go to this repository: https://github.com/AoifeHughes/MMO_Simulator
2. Navigate to Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Name: `BLOG_DEPLOY_TOKEN`
5. Value: Paste the token you copied
6. Click "Add secret"

### 4. Enable GitHub Pages (Optional - for gh-pages branch)

If you want docs accessible at `https://aoifehughes.github.io/MMO_Simulator/`:

1. Go to repository Settings → Pages
2. Source: Deploy from a branch
3. Branch: `gh-pages` / `/ (root)`
4. Click Save

The workflow will create the `gh-pages` branch automatically on first run.

### 5. Trigger Documentation Build

#### Option A: Push to Main

```bash
git add docs/ .github/workflows/docs.yml .gitignore requirements.txt DOCUMENTATION_SETUP.md
git commit -m "Add Sphinx documentation with ReadTheDocs theme and CI/CD"
git push origin main
```

#### Option B: Manual Trigger

1. Go to Actions tab in GitHub
2. Select "Build and Deploy Documentation" workflow
3. Click "Run workflow" → "Run workflow"

### 6. Verify Deployment

After the workflow completes (2-3 minutes):

1. **GitHub Pages**: https://aoifehughes.github.io/MMO_Simulator/
2. **Hugo Blog**: https://aoifehughes.github.io/mmo-simulator/

Check the Actions tab for build status and logs.

## 📝 Updating Documentation

### Add New Documentation Pages

1. Create `.rst` file in appropriate `docs/source/` subdirectory
2. Add to relevant `index.rst` toctree:

```rst
.. toctree::
   :maxdepth: 2

   new-section/new-page
```

3. Rebuild locally to test:

```bash
cd docs
make html
```

4. Commit and push - deployment is automatic!

### Update Existing Pages

Simply edit the `.rst` files and push. Documentation rebuilds automatically.

### Update API Reference

API docs are auto-generated from Python docstrings. To update:

1. Add/modify docstrings in Python source files
2. Push changes - autodoc will regenerate API docs

Example docstring format:

```python
def my_function(param1: str, param2: int) -> bool:
    """Brief description.

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

## 🎨 Customization

### Custom CSS

Edit `docs/source/_static/custom.css` for styling changes.

### Theme Configuration

Edit `docs/source/conf.py`:

```python
html_theme_options = {
    'logo_only': False,
    'display_version': True,
    'style_nav_header_background': '#2980B9',  # Change header color
    # ... more options
}
```

### Add Logo/Favicon

1. Add image files to `docs/source/_static/`
2. Update `conf.py`:

```python
html_logo = '_static/logo.png'
html_favicon = '_static/favicon.ico'
```

## 🔍 Workflow Details

### What Triggers Builds

- Push to `main` branch with changes to:
  - `docs/**` (any documentation files)
  - `simulation_framework/**/*.py` (Python source for autodoc)
  - `.github/workflows/docs.yml` (workflow itself)
- Pull requests to `main` (build only, no deploy)
- Manual workflow dispatch

### Deployment Targets

**1. gh-pages Branch (GitHub Pages)**
- URL: `https://aoifehughes.github.io/MMO_Simulator/`
- Updates: Automatic on push to main
- Uses: `peaceiris/actions-gh-pages@v3`

**2. Hugo Blog Integration**
- URL: `https://aoifehughes.github.io/mmo-simulator/`
- Location: `AoifeHughes.github.io/static/mmo-simulator/`
- Updates: Automatic on push to main
- Uses: Personal Access Token (`BLOG_DEPLOY_TOKEN`)

### Build Artifacts

Documentation HTML is uploaded as GitHub Actions artifact (retained 7 days) for inspection.

## 🐛 Troubleshooting

### Build Fails

1. Check Actions tab for error logs
2. Test locally: `cd docs && make html`
3. Common issues:
   - Missing dependencies: `pip install -r docs/requirements.txt`
   - Import errors: Check `sys.path` in `conf.py`
   - RST syntax errors: Look for `WARNING` in build output

### Deployment Fails

1. Verify `BLOG_DEPLOY_TOKEN` secret exists and is valid
2. Check token has `repo` scope
3. Verify blog repository URL in workflow: `AoifeHughes/AoifeHughes.github.io`
4. Check Actions logs for specific error

### Documentation Not Showing on Blog

1. Verify Hugo is configured to copy `static/` directory
2. Check Hugo build logs
3. Manually verify files exist: `blog/static/mmo-simulator/index.html`
4. Clear browser cache and try again

### GitHub Pages Not Working

1. Enable GitHub Pages in repository Settings → Pages
2. Select `gh-pages` branch
3. Wait a few minutes for Pages to build
4. Check Pages build status in Settings → Pages

## 📚 Documentation Resources

- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [ReadTheDocs Theme](https://sphinx-rtd-theme.readthedocs.io/)
- [RST Syntax Guide](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html)
- [Sphinx Autodoc](https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html)

## ✅ Success Checklist

- [ ] Documentation builds locally (`make html` succeeds)
- [ ] GitHub secret `BLOG_DEPLOY_TOKEN` configured
- [ ] Pushed to main branch
- [ ] GitHub Actions workflow completed successfully
- [ ] Documentation visible at `https://aoifehughes.github.io/mmo-simulator/`
- [ ] (Optional) GitHub Pages enabled and working

## 🎉 Next Steps

1. **Add Content**: Expand tutorials, add more examples
2. **Add Images**: Screenshots, diagrams, GIFs in `_static/`
3. **Version Docs**: Use git tags for version-specific docs
4. **Link from Blog**: Add navigation link in Hugo site
5. **Share**: Link documentation in README, papers, presentations

---

**Questions?** Check the workflow logs in the Actions tab or open an issue.
