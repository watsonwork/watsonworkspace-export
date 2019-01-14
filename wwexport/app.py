import tkinter as tk


import logging
from Tkinter import INSERT

class WidgetLogger(logging.Handler):
    def __init__(self, widget):
        logging.Handler.__init__(self)
        self.widget = widget

    def emit(self, record):
        # Append message (record) to the widget
        self.widget.insert(INSERT, record + '\n')

class ExportApp(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()

    def create_widgets(self):
        self.accept_b = tk.Button(self, text="Accept",
                                  command=self.accept_terms)
        self.accept_b.pack(side="left")

        self.quit = tk.Button(self, text="Reject and Quit", fg="red",
                              command=self.master.destroy)
        self.quit.pack(side="right")

    def accept_terms(self):
        print("Accepted!!")


root = tk.Tk()
app = Application(master=root)

app.mainloop()
