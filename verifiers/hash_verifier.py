import hashlib
import os

try:
    from PIL import Image
    import imagehash
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

def get_file_hash(file_path: str) -> str:
    if not os.path.exists(file_path):
        return None
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def get_image_phash(file_path: str) -> str:
    if not PIL_AVAILABLE:
        return get_file_hash(file_path)
    try:
        img = Image.open(file_path)
        return str(imagehash.phash(img))
    except Exception:
        return None

def check_files_exist(file_paths: list) -> list:
    return [{"path": p, "exists": os.path.exists(p)} for p in file_paths]

def check_unique_images(file_paths: list) -> dict:
    hashes = {}
    duplicates = []
    for path in file_paths:
        h = get_image_phash(path)
        if h is None:
            continue
        if h in hashes:
            duplicates.append({"file": path, "duplicate_of": hashes[h]})
        else:
            hashes[h] = path
    return {
        "all_unique": len(duplicates) == 0,
        "duplicates": duplicates,
        "total_checked": len(file_paths)
    }