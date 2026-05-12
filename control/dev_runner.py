import os
import time
import subprocess

def run_main():
    print("Running main.py")
    return subprocess.Popen(["python", "main.py"])

if __name__ == "__main__":
    last_mtime = os.path.getmtime("main.py")
    process = run_main()

    try:
        while True:
            time.sleep(1)
            new_mtime = os.path.getmtime("main.py")
            if new_mtime != last_mtime:
                print("Detected change in main.py. Restarting...")
                process.terminate()
                process.wait()
                process = run_main()
                last_mtime = new_mtime
    except KeyboardInterrupt:
        print("Stopping...")
        process.terminate()