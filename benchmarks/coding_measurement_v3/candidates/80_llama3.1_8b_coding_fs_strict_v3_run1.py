import os
from collections import defaultdict
from operator import itemgetter

def walk_directory(directory):
    """Walk the directory and compute statistics"""
    stats = {"total_files": 0, "total_directories": 1, "total_size_bytes": 0}
    extension_count = defaultdict(int)
    file_sizes = []
    
    for root, dirs, files in os.walk(directory):
        for dir in dirs:
            stats["total_directories"] += 1
        for filename in files:
            filepath = os.path.join(root, filename)
            stats["total_files"] += 1
            stats["total_size_bytes"] += os.path.getsize(filepath)
            
            file_extension = "." + os.path.splitext(filename)[1][1:]
            if file_extension:
                extension_count[file_extension] += 1
            
            file_sizes.append((filepath, os.path.getsize(filepath)))
    
    # Build extension distribution
    sorted_extensions = sorted(extension_count.items(), key=itemgetter(0))
    for ext in sorted_extensions:
        extension_count[ext[0]] = ext[1]
    
    return stats, sorted_extensions, file_sizes

def build_extension_distribution(stats, sorted_extensions):
    """Build a dictionary where keys are extensions and values are counts"""
    distribution = {}
    no_ext_count = 0
    
    for (ext, count) in sorted_extensions:
        if count > 0:
            distribution[ext] = count
        else:
            no_ext_count += stats["total_files"]
    
    # Ensure [no_ext] is included in the output
    if no_ext_count > 0:
        distribution[".txt"] = no_ext_count

def compute_largest_files(file_sizes):
    """Compute and return a list of the 3 largest files"""
    file_sizes.sort(key=itemgetter(1), reverse=True)
    
    # In case of ties, sort by relative path
    tied_files = []
    max_size = file_sizes[0][1]
    for (filepath, size) in file_sizes:
        if size == max_size:
            tied_files.append(filepath)
        else:
            break
    
    largest_files = file_sizes[:3] + [(file, size) for file, size in zip(tied_files, [max_size]*len(tied_files))]
    
    return largest_files

def compute_top_directories(file_count):
    """Compute and return a list of the top 3 directories by direct file count"""
    directory_counts = defaultdict(int)
    current_dir_path = ""
    
    for root, dirs, files in os.walk("."):
        if root == ".":
            continue
        
        relative_path = os.path.relpath(root, ".")
        
        for dir in dirs:
            dir_path = os.path.join(relative_path, dir)
            directory_counts[dir_path] += 0  # Count files directly inside each directory
        for filename in files:
            file_path = os.path.join(root, filename)
            current_dir_path = os.path.dirname(file_path)
    
    top_directories = sorted(directory_counts.items(), key=itemgetter(1), reverse=True)[:3]
    return top_directories

def main():
    """Main function"""
    if len(os.sys.argv) < 2:
        print("Error: directory path must be provided as an argument")
        exit()
    
    directory_path = os.path.abspath(os.sys.argv[1])
    
    stats, sorted_extensions, file_sizes = walk_directory(directory_path)
    
    # Build extension distribution
    build_extension_distribution(stats, sorted_extensions)
    
    # Compute largest files
    largest_files = compute_largest_files(file_sizes)
    
    # Compute top directories by direct file count
    top_directories = compute_top_directories(stats["total_files"])
    
    # Compute checksum
    checksum = stats["total_size_bytes"] % 1000000
    
    print(f"=== SUMMARY ===")
    print(f"Total files: {stats['total_files']}")
    print(f"Total directories: {stats['total_directories']}")
    print(f"Total size: {stats['total_size_bytes']} bytes")

    print("\n=== EXTENSION DISTRIBUTION ===")
    for ext, count in sorted_extension_count.items():
        if ext == ".txt":
            print(f"{ext}: {no_ext_count}")
        else:
            print(f"{ext}: {count}")

    print("\n=== LARGEST FILES ===")
    for file_size in largest_files[:3]:
        path = os.path.relpath(file_size[0], directory_path)
        print(f"{path} - {file_size[1]} bytes")

    print("\n=== TOP DIRECTORIES BY DIRECT FILE COUNT ===")
    for dir, count in top_directories:
        relative_path = os.path.relpath(dir, directory_path)
        print(f"{relative_path} - {count} files")

    print("\n=== FINAL CHECKSUM ===")
    print(f"Checksum: {checksum}")

if __name__ == "__main__":
    main()
