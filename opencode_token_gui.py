import tkinter as tk

from opencode_token_app.gui import OpenCodeTokenApp


def main():
    root = tk.Tk()
    root.title("OpenCode Token 图形界面")
    root.geometry("1400x900")
    OpenCodeTokenApp(root, entry_path=__file__)
    root.mainloop()


if __name__ == "__main__":
    main()
