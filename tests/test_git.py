# SPDX-FileCopyrightText: 2024 Ledger SAS
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from pathlib import Path
from random import choices
from string import ascii_letters

from git import Repo
from git.exc import GitCommandError

from barbican.scm import Git


class GitTestBase:
    @pytest.fixture(scope="class")
    def private_dir(self, tmp_path_factory):
        return tmp_path_factory.mktemp(type(self).__name__)

    @pytest.fixture(scope="class")
    def clone_dir(self, private_dir):
        filename = private_dir / "cloned"
        return filename

    def add_and_commit_random_file(self, repo):
        file = Path(repo.working_tree_dir, "".join(choices(ascii_letters, k=16)))
        file.touch()
        repo.index.add(file)
        repo.index.commit(f"Adding {file.name}")

    @pytest.fixture(scope="class")
    def origin(self, private_dir):
        origin_dir = private_dir / "origin"
        # initialize empty git repository
        origin_repo = Repo.init(origin_dir)
        self.add_and_commit_random_file(origin_repo)
        return origin_repo

    @pytest.fixture(scope="class")
    def default_branch(self, origin):
        # master by default, until git v2.28, this is hardcoded.
        # from git v2.28, this can be changed through `init.defaultBranch`
        default_branch = "master"
        major, minor, _ = origin.git.version_info
        if major >= 2 and minor >= 28:
            try:
                default_branch = origin.git.config(["--global", "init.defaultBranch"])
            except GitCommandError:
                pass
        return default_branch


class GitTestProjectMock:
    class _Parent:
        class _Path:
            def __init__(self, src_dir):
                self.src_dir = src_dir

        def __init__(self, src_dir):
            self.path = GitTestProjectMock._Parent._Path(src_dir)

    def __init__(self, path, name, url, revision):
        self.url = url
        self.name = name
        self.revision = revision
        self.src_dir = path / name
        self.parent = GitTestProjectMock._Parent(path)

    def post_update_hook(self): ...
    def post_download_hook(self): ...


class TestGit(GitTestBase):
    @pytest.mark.dependency()
    def test_download_branch_ref(self, private_dir, origin, default_branch):
        prj_mock = GitTestProjectMock(private_dir, "test", origin.git_dir, default_branch)
        repo = Git(prj_mock)
        repo.download()
        assert repo._repo.head.commit == origin.head.commit
        self.add_and_commit_random_file(origin)
        assert repo._repo.head.commit != origin.head.commit

    @pytest.mark.dependency(depends=["TestGit::test_download_branch_ref"])
    def test_update_same_branch(self, private_dir, origin, default_branch):
        prj_mock = GitTestProjectMock(private_dir, "test", origin.git_dir, default_branch)
        repo = Git(prj_mock)
        assert repo._repo.head.commit != origin.head.commit
        repo.update()
        assert repo._repo.head.commit == origin.head.commit
        self.add_and_commit_random_file(origin)
        assert repo._repo.head.commit != origin.head.commit

    @pytest.mark.dependency(depends=["TestGit::test_update_same_branch"])
    def test_update_to_commit(self, private_dir, origin):
        prj_mock = GitTestProjectMock(private_dir, "test", origin.git_dir, str(origin.head.commit))
        repo = Git(prj_mock)
        assert repo._repo.head.commit != origin.head.commit
        repo.update()
        assert repo._repo.head.commit == origin.head.commit
        self.add_and_commit_random_file(origin)
        assert repo._repo.head.commit != origin.head.commit

    @pytest.mark.dependency(depends=["TestGit::test_update_same_branch"])
    def test_update_from_commit_to_branch(self, private_dir, origin, default_branch):
        prj_mock = GitTestProjectMock(private_dir, "test", origin.git_dir, default_branch)
        repo = Git(prj_mock)
        assert repo._repo.head.commit != origin.head.commit
        repo.update()
        assert repo._repo.head.commit == origin.head.commit
        self.add_and_commit_random_file(origin)
        assert repo._repo.head.commit != origin.head.commit

    @pytest.mark.dependency()
    def test_download_commit(self, private_dir, origin):
        commit = origin.head.commit
        prj_mock = GitTestProjectMock(private_dir, "test_commit", origin.git_dir, str(commit))
        repo = Git(prj_mock)
        self.add_and_commit_random_file(origin)
        repo.download()
        assert repo._repo.head.commit == commit
        assert repo._repo.head.commit != origin.head.commit

    def test_download_invalid_ref(self, private_dir, origin):
        with pytest.raises(Exception):
            prj_mock = GitTestProjectMock(
                private_dir, "test_invalid_ref", origin.git_dir, "pouette"
            )
            repo = Git(prj_mock)
            repo.download()

    def test_download_invalid_commit(self, private_dir, origin):
        with pytest.raises(Exception):
            prj_mock = GitTestProjectMock(
                private_dir, "test_invalid_commit", origin.git_dir, str("a" * 40)
            )
            repo = Git(prj_mock)
            repo.download()
