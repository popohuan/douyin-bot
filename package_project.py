# -*- coding: utf-8 -*-
import os
import zipfile
import sys

def package_project():
    output_zip = "bot_douyin_release.zip"
    if os.path.exists(output_zip):
        try:
            os.remove(output_zip)
        except Exception:
            pass

    include_files = [
        "server.py",
        "bot_manager.py",
        "database.py",
        "llm_service.py",
        "login_helper.py",
        "login_browser.py",
        "login_browser.bat",
        "run_login.py",
        "requirements.txt",
        "start_windows.bat",
        "start_linux.sh",
        "USAGE_GUIDE.md",
        "ARCHITECTURE_AND_IMPLEMENTATION.md",
        "bot_douyin.db"
    ]

    include_dirs = ["static", "douyin_session"]

    # 排除庞大的临时缓存与锁文件
    exclude_patterns = [
        "Cache", "Cache_Data", "Code Cache", "GPUCache", "DawnCache", 
        "Crashpad", "lockfile", ".tmp", "__pycache__", ".git"
    ]

    print(f"正在创建项目完整发行包: {output_zip} ...")
    added_count = 0

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 添加根目录生产文件
        for f in include_files:
            if os.path.exists(f):
                zf.write(f, arcname=f)
                added_count += 1
                print(f" [+] 添加核心文件: {f}")

        # 添加目录
        for d in include_dirs:
            if not os.path.exists(d):
                continue
            for root, dirs, files in os.walk(d):
                # 过滤排除目录
                dirs[:] = [sub for sub in dirs if not any(pat.lower() in sub.lower() for pat in exclude_patterns)]
                for file in files:
                    if any(pat.lower() in file.lower() for pat in exclude_patterns):
                        continue
                    full_p = os.path.join(root, file)
                    arc_p = os.path.relpath(full_p, ".")
                    try:
                        zf.write(full_p, arcname=arc_p)
                        added_count += 1
                    except PermissionError:
                        print(f" [-] 忽略运行中锁定的临时文件: {arc_p}")
                    except Exception as e:
                        print(f" [-] 跳过文件 {arc_p}: {e}")

    size_mb = os.path.getsize(output_zip) / (1024 * 1024)
    print("=" * 60)
    print(f"[+] 项目打包完成！")
    print(f"输出路径: {os.path.abspath(output_zip)}")
    print(f"包含文件数: {added_count}")
    print(f"压缩包体积: {size_mb:.2f} MB")
    print("=" * 60)

if __name__ == "__main__":
    package_project()
