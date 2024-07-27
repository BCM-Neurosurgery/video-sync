import os
import tkinter as tk
from tkinter import filedialog


def clear_screen():
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


def welcome_screen():
    clear_screen()
    print("\nWelcome to Video Sync Program v1.0")
    print("Please select an option:")
    print("1. Load a config file")
    print("2. Exit")
    choice = input("Enter your choice: ")
    return choice


def select_config_file():
    root = tk.Tk()
    root.withdraw()
    config_file_path = filedialog.askopenfilename(
        title="Select Configuration File",
        filetypes=(("YAML files", "*.yaml"), ("All files", "*.*")),
    )
    root.destroy()
    return config_file_path


def select_config():
    clear_screen()
    print("Please select YAML config file")
    config_path = select_config_file()
    return config_path


def prompt_user_for_video_file(cam_mp4_files):
    """Prompt the user to select a video file from the list."""
    if not cam_mp4_files:
        print("No video files found.")
        return None

    print("Available video files:")
    for idx, file in enumerate(cam_mp4_files):
        print(f"{idx + 1}: {file}")

    while True:
        try:
            choice = int(
                input(
                    "Enter the number of the file you want to process, or type 0 to go back to previous menu: "
                )
            )
            if choice == 0:
                return choice
            elif 1 <= choice <= len(cam_mp4_files):
                return cam_mp4_files[choice - 1]
            else:
                print(f"Please enter a number between 0 and {len(cam_mp4_files)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")


def mode_selection_screen():
    clear_screen()
    print("\nPlease select the following mode to sync:")
    print("1. Load UTC timestmaps from a CSV file")
    print("2. Manually select an exisiting video (Legacy)")
    print("Enter 0 to go back to previous screen.")
    choice = input("Enter your choice: ")
    return choice


def select_csv_file():
    root = tk.Tk()
    root.withdraw()
    csv_file_path = filedialog.askopenfilename(
        title="Select CSV File",
        filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
    )
    root.destroy()
    return csv_file_path
