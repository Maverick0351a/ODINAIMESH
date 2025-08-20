---
name: 📋 Pull Request
about: Submit a pull request to contribute to ODIN Protocol
title: ''
labels: ''
assignees: ''
---

## 🎯 Description
Brief description of what this PR does.

## 🔗 Related Issue
Fixes #(issue number) or Closes #(issue number)

## 🧪 Type of Change
Please check the relevant option(s):

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)  
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🔧 Refactoring (no functional changes)
- [ ] ⚡ Performance improvement
- [ ] 🧪 Test improvements
- [ ] 🏗️ Infrastructure/build changes

## 🧪 Testing
Describe how you tested your changes:

- [ ] All existing tests pass
- [ ] Added new tests for new functionality
- [ ] Tested manually (describe scenarios)
- [ ] Integration tests pass
- [ ] Performance impact assessed

**Test commands run:**
```bash
python -m pytest
npm -C packages/sdk test
```

## 📋 Checklist
Please check all applicable items:

### Code Quality
- [ ] Code follows the project's style guidelines
- [ ] Self-review of code completed
- [ ] Code is well-commented, particularly complex areas
- [ ] No unnecessary console.log/print statements
- [ ] No commented-out code blocks

### Documentation
- [ ] Updated relevant documentation
- [ ] Added/updated docstrings for new functions
- [ ] Updated README if necessary
- [ ] Added examples for new features

### Security
- [ ] No sensitive information exposed
- [ ] Input validation added where needed
- [ ] Security implications considered
- [ ] No new security vulnerabilities introduced

### Performance
- [ ] Performance impact considered
- [ ] No memory leaks introduced
- [ ] Database queries optimized (if applicable)
- [ ] Caching strategy considered (if applicable)

## 📸 Screenshots (if applicable)
Add screenshots or GIFs to demonstrate visual changes.

## 🔄 Breaking Changes
If this is a breaking change, describe:
- What breaks
- Migration path for users
- Deprecation timeline (if applicable)

## 📝 Additional Notes
Any additional information, considerations, or context that reviewers should know.

## 🏷️ Deployment Notes
Special deployment considerations or environment variables needed.

---

**For Maintainers:**
- [ ] Review completed
- [ ] Tests passing in CI
- [ ] Documentation updated
- [ ] Security review completed (if needed)
- [ ] Performance review completed (if needed)
- [ ] Ready to merge
