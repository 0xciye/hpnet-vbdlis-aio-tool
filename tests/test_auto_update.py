from auto_update import cleanup_legacy_previous_dirs


def test_cleanup_legacy_previous_dirs_removes_only_known_backup_names(tmp_path):
    current = tmp_path / "Công cụ đang dùng"
    current.mkdir()
    (tmp_path / "Công cụ đang dùng.previous").mkdir()
    (tmp_path / "Công cụ đang dùng.previous-0123456789abcdef0123456789abcdef").mkdir()
    (tmp_path / "Công cụ đang dùng.previous-keep-me").mkdir()
    (tmp_path / "other.previous").mkdir()

    removed = cleanup_legacy_previous_dirs(current)

    assert {path.name for path in removed} == {
        "Công cụ đang dùng.previous",
        "Công cụ đang dùng.previous-0123456789abcdef0123456789abcdef",
    }
    assert (tmp_path / "Công cụ đang dùng").is_dir()
    assert (tmp_path / "Công cụ đang dùng.previous-keep-me").is_dir()
    assert (tmp_path / "other.previous").is_dir()
