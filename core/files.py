import os
import mimetypes

HOME_DIR = os.path.expanduser("~")
SKIP_DIRS = {'.git', '.venv', '__pycache__', 'node_modules', '.cache', 'tmp'}

class FileSearcher:
    def __init__(self):
        pass

    def search(self, query, limit=50):
        if not query or len(query) < 2:
            return []
        
        results = []
        # Search in Home directory (recursive but shallow or limited depth could be better for performance)
        # For now, let's just do a standard walk but stop if we find enough
        # Optimization: Only search specific user folders? Documents, Pictures, Downloads, Videos
        
        search_roots = [
            os.path.join(HOME_DIR, "Documents"),
            os.path.join(HOME_DIR, "Downloads"),
            os.path.join(HOME_DIR, "Pictures"),
            os.path.join(HOME_DIR, "Videos"),
            os.path.join(HOME_DIR, "Music"),
            os.path.join(HOME_DIR, "Desktop"),
            os.path.join(HOME_DIR, "Projects"), # Custom common one
        ]
        
        query_lower = query.lower()
        
        count = 0
        for root_dir in search_roots:
            if not os.path.exists(root_dir):
                continue
                
            for root, dirs, files in os.walk(root_dir):
                # Filter out hidden/skip dirs
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS]
                
                for file in files:
                    if query_lower in file.lower():
                        full_path = os.path.join(root, file)
                        mime_type, _ = mimetypes.guess_type(full_path)
                        
                        file_type = "File"
                        if mime_type:
                            if mime_type.startswith("image/"):
                                file_type = "Image"
                            elif mime_type.startswith("video/"):
                                file_type = "Video"
                        
                        results.append({
                            "name": file,
                            "path": full_path,
                            "type": file_type,
                            "mime": mime_type
                        })
                        count += 1
                        if count >= limit:
                            return results
        return results
