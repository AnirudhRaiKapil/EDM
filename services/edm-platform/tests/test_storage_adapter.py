from app.modules.storage.adapter import LocalDiskStorageAdapter


def test_save_raw_upload_strips_path_components_from_filename(tmp_path):
    adapter = LocalDiskStorageAdapter(root=tmp_path)

    relative_path = adapter.save_raw_upload(
        "source-1", "C:\\Users\\someone\\AppData\\Local\\Temp\\customers.csv", b"a,b\n1,2\n"
    )

    assert relative_path == "raw/source-1/customers.csv"
    assert (tmp_path / relative_path).read_bytes() == b"a,b\n1,2\n"


def test_save_raw_upload_rejects_traversal_in_filename(tmp_path):
    adapter = LocalDiskStorageAdapter(root=tmp_path)

    relative_path = adapter.save_raw_upload("source-1", "../../evil.csv", b"x")

    assert relative_path == "raw/source-1/evil.csv"
    assert (tmp_path / relative_path).is_file()
    assert not (tmp_path.parent.parent / "evil.csv").exists()
