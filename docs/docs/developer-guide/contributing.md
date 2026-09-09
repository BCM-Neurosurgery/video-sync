# 🤝 Contributing Guide

We welcome contributions to improve video-sync! Follow these steps to contribute:

Note: This guide assumes basic familiarity with Git, Python, and command-line environments. 

## 1: Fork & Clone the Repository

Click the Fork button at the top right of the GitHub repository

Clone your fork
```sh
git clone https://github.com/YOUR_USERNAME/video-sync.git
cd video-sync
```

Set the upstream remote

```sh
git remote add upstream https://github.com/bcm-neurosurgery/video-sync.git
```
    
## 2: Set Up Your Environment

Please refer to [installations guide](../installation.md)

Verify installation
```sh
stitch-videos --help
```
   
## 3: Create a Branch

Before making any changes, create a new branch:

```sh
git checkout -b feature/my-awesome-feature
```

For bug fixes, use:

```
git checkout -b fix/issue-123
```

Replace my-awesome-feature or issue-123 with a meaningful name.

## 4: Make Changes & Test

Write your code and make changes. Run tests to ensure everything works:

Format your code with:
```sh
black .
```

## 5: Commit and Push

Stage and commit your changes

```sh
git add .
git commit -m "Add feature: my awesome feature"
```

Push your branch to GitHub

```sh    
git push origin feature/my-awesome-feature
```

## 6: Submit a Pull Request

Go to your fork on GitHub.
Click the "New Pull Request" button.
Select your branch and compare it with the main branch.
Write a clear description of your changes.
Click "Create Pull Request".

Yewen will review your code and provide feedback if needed.

## 7: Keep Your Fork Updated

To avoid merge conflicts, keep your local repository updated with the latest changes:

```sh
git checkout main
git pull upstream main
git checkout feature/my-awesome-feature
git merge main
```

## Contribution Guidelines

- Follow [PEP 8](https://peps.python.org/pep-0008/) for Python code style.
- Write clear commit messages.
- Keep pull requests focused—one feature or bug fix per PR.
- Add comments and docstrings where necessary.
- If modifying behavior, update documentation and tests.

Happy coding! Thank you for improving video-sync!
