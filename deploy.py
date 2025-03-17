import os
import zipfile

def zip_folder(folder_path, output_zip):
    """
    Zips the contents of folder_path into a zip file named output_zip.
    
    Args:
        folder_path (str): The path of the folder to zip.
        output_zip (str): The path of the output zip file.
    """
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Walk the directory tree and add files to the zip file.
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                # Create an archive name relative to the parent directory of the folder.
                arcname = os.path.relpath(file_path, start=os.path.dirname(folder_path))
                zipf.write(file_path, arcname)

def main():
    # Determine the directory where the script is located.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    folder_name = "Source2Utilities"
    folder_path = os.path.join(script_dir, folder_name)
    output_zip = os.path.join(script_dir, f"{folder_name}.zip")
    
    # Check if the folder exists.
    if not os.path.exists(folder_path):
        print(f"Error: The folder '{folder_path}' does not exist.")
        return
    
    # Create the zip archive.
    try:
        zip_folder(folder_path, output_zip)
        print(f"Successfully zipped '{folder_name}' into '{output_zip}'.")
    except Exception as e:
        print(f"An error occurred while zipping the folder: {e}")

if __name__ == "__main__":
    main()