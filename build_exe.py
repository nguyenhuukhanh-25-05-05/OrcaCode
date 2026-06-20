import os
import sys
import subprocess
import shutil

def main():
    print("==================================================")
    print("   OrcaCode Standalone EXE Packager using PyInstaller")
    print("==================================================")
    
    # 1. Install pyinstaller if not present
    try:
        import PyInstaller
        print("[1/3] PyInstaller is already installed.")
    except ImportError:
        print("[1/3] PyInstaller not found. Installing via pip...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
            print("      Successfully installed PyInstaller.")
        except Exception as e:
            print(f"ERROR: Failed to install PyInstaller: {e}")
            sys.exit(1)

    # 2. Check and download rg.exe so it can be bundled
    rg_exists = os.path.exists("rg.exe")
    if not rg_exists:
        print("[2/3] Standalone rg.exe not found in root. Downloading to bundle...")
        url = "https://github.com/BurntSushi/ripgrep/releases/download/14.1.0/ripgrep-14.1.0-x86_64-pc-windows-msvc.zip"
        import urllib.request
        import zipfile
        import tempfile
        
        zip_path = os.path.join(tempfile.gettempdir(), "ripgrep.zip")
        extract_dir = os.path.join(tempfile.gettempdir(), "ripgrep_extracted")
        
        try:
            print("      Downloading ripgrep zip from GitHub...")
            urllib.request.urlretrieve(url, zip_path)
            
            print("      Extracting zip...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find rg.exe in extracted folder
            found_rg = False
            for root, dirs, files in os.walk(extract_dir):
                if "rg.exe" in files:
                    shutil.copy(os.path.join(root, "rg.exe"), ".")
                    found_rg = True
                    break
                    
            if found_rg:
                print("      Successfully downloaded and prepared rg.exe for bundling!")
            else:
                print("      WARNING: rg.exe not found in downloaded zip.")
        except Exception as e:
            print(f"      WARNING: Failed to download rg.exe: {e}. Packaging will continue without bundled ripgrep.")
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
    else:
        print("[2/3] Standalone rg.exe found in root. Ready to bundle.")

    # 3. Build standalone EXE using PyInstaller
    print("[3/3] Compiling standalone executable with PyInstaller...")
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name=orca",
        "--collect-all=textual",
        "--collect-all=rich",
        "--collect-all=rapidfuzz"
    ]
    
    if os.path.exists("rg.exe"):
        # Add rg.exe as a binary asset (semi-colon is used on Windows)
        cmd.append('--add-binary=rg.exe;.')
        
    cmd.append("orca.py")
    
    print(f"      Running command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("\n==================================================")
        print(" SUCCESS: Standalone executable created successfully!")
        print(f" Location: {os.path.abspath('dist/orca.exe')}")
        print("==================================================")
    except Exception as e:
        print(f"\nERROR: PyInstaller packaging failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
