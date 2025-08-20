# Contributing to ODIN Protocol

Thank you for your interest in contributing to ODIN Protocol! This document provides guidelines and information for contributors.

## 🚀 Quick Start for Contributors

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a branch** for your feature/fix
4. **Make your changes** following our guidelines
5. **Test thoroughly** using our test suite
6. **Submit a pull request**

## 🏗️ Development Setup

### Prerequisites
- Python 3.8+
- Node.js 16+ (for JavaScript SDK)
- Git
- Docker (optional, for containerized testing)

### Local Development Environment
```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/ODINAIMESH.git
cd ODINAIMESH

# Install Python dependencies
pip install -r requirements.txt

# Install JavaScript dependencies
npm install -C packages/sdk
npm install -C packages/langchain-odin-tools

# Run tests to verify setup
python -m pytest
npm -C packages/sdk test
```

## 🧪 Testing

We maintain comprehensive test coverage across all components:

### Python Tests
```bash
# Run all Python tests
python -m pytest

# Run specific test suites
python -m pytest apps/gateway/tests/
python -m pytest apps/agent_beta/tests/
python -m pytest libs/odin_core/tests/

# Run with coverage
python -m pytest --cov=apps --cov=libs --cov-report=html
```

### JavaScript Tests
```bash
# Run SDK tests
npm -C packages/sdk test

# Run LangChain tools tests
npm -C packages/langchain-odin-tools test
```

### E2E Tests
```bash
# Run end-to-end integration tests
python -m pytest tests/e2e/
```

## 📝 Code Style and Standards

### Python Code Style
- Follow **PEP 8** formatting
- Use **Black** for code formatting: `black .`
- Use **isort** for import sorting: `isort .`
- Use **flake8** for linting: `flake8 .`
- Type hints are encouraged using **mypy**

### JavaScript/TypeScript Code Style
- Follow **Prettier** formatting
- Use **ESLint** for linting
- Maintain TypeScript type safety

### Documentation
- Document all public APIs with docstrings
- Include examples in docstrings where helpful
- Update README files when adding new features
- Add inline comments for complex logic

## 🏗️ Architecture Guidelines

### Code Organization
- **apps/**: Standalone applications (gateway, agent_beta)
- **libs/**: Reusable libraries and core protocol implementation
- **services/**: Microservices (relay)
- **packages/**: SDK packages and tools
- **tests/**: Integration and E2E tests

### API Design Principles
- RESTful design where applicable
- Consistent error handling and status codes
- Comprehensive input validation
- Proper HTTP status codes and error messages

### Security Guidelines
- All endpoints must validate inputs
- Authentication/authorization where required
- No sensitive data in logs
- Follow secure coding practices

## 🐛 Issue Reporting

### Bug Reports
When reporting bugs, please include:
- **Clear description** of the issue
- **Steps to reproduce** the problem
- **Expected vs actual behavior**
- **Environment details** (OS, Python version, etc.)
- **Log output** if applicable
- **Minimal reproduction case**

### Feature Requests
When requesting features, please include:
- **Clear description** of the feature
- **Use case** and motivation
- **Proposed API** or interface (if applicable)
- **Alternative solutions** you've considered

## 🔄 Pull Request Process

### Before Submitting
1. **Run all tests** and ensure they pass
2. **Add tests** for new functionality
3. **Update documentation** as needed
4. **Follow commit message conventions**
5. **Rebase** your branch on the latest main

### Commit Messages
Use conventional commits format:
```
type(scope): description

[optional body]

[optional footer]
```

Examples:
- `feat(gateway): add new bridge endpoint`
- `fix(agent-beta): resolve HTTP signature validation`
- `docs(readme): update installation instructions`
- `test(core): add envelope validation tests`

### Pull Request Template
- **Description**: What does this PR do?
- **Type of Change**: Bug fix, feature, documentation, etc.
- **Testing**: How was this tested?
- **Breaking Changes**: Any breaking changes?
- **Checklist**: Completed all requirements?

## 📚 Areas for Contribution

### 🔧 Core Development
- Gateway endpoint implementations
- Agent Beta service enhancements
- Core protocol library improvements
- Security feature development

### 📖 Documentation
- API documentation improvements
- Tutorial and guide creation
- Code example development
- Architecture documentation

### 🧪 Testing
- Test coverage improvements
- Performance testing
- Security testing
- Integration test scenarios

### 🌐 SDKs and Tools
- SDK feature enhancements
- New language SDK development
- Tool integrations (LangChain, etc.)
- CLI tool improvements

### ☁️ Infrastructure
- Deployment automation
- Monitoring and observability
- Cloud platform integrations
- Container optimizations

## 🏆 Recognition

Contributors will be:
- **Listed** in our contributors file
- **Mentioned** in release notes for significant contributions
- **Invited** to our contributor Discord channel
- **Eligible** for contributor swag (coming soon!)

## 📞 Getting Help

- **Discord**: Join our [contributor channel](https://discord.gg/odin-protocol)
- **GitHub Issues**: For technical questions and discussions
- **Email**: For private matters: contributors@odin-protocol.org

## 📋 Contributor License Agreement

By contributing to ODIN Protocol, you agree that:
- Your contributions will be licensed under the same license as the project
- You have the right to contribute the code/documentation
- Your contributions are your original work

## 🌟 Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:
- **Be respectful** and considerate
- **Be collaborative** and helpful
- **Be patient** with newcomers
- **Focus on** constructive feedback

Unacceptable behavior includes harassment, discrimination, or disruptive conduct.

---

Thank you for contributing to ODIN Protocol! Your efforts help build the future of AI agent communication. 🚀
