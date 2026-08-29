import hashlib
import tkinter as tk
from tkinter import messagebox, scrolledtext

# Blockchain list
blockchain = []

# Hash function
def create_hash(data):
    return hashlib.sha256(data.encode()).hexdigest()

# Add block
def add_block():
    data = entry.get()
    if not data:
        messagebox.showwarning("Warning", "Enter some data")
        return

    prev_hash = blockchain[-1]['hash'] if blockchain else '0'
    block_data = data + prev_hash
    block_hash = create_hash(block_data)

    block = {
        'data': data,
        'prev_hash': prev_hash,
        'hash': block_hash
    }

    blockchain.append(block)
    entry.delete(0, tk.END)
    display_chain()

# Display blockchain
def display_chain():
    text_area.delete(1.0, tk.END)
    for i, block in enumerate(blockchain):
        text_area.insert(tk.END, f"Block {i+1}\n")
        text_area.insert(tk.END, f"Data: {block['data']}\n")
        text_area.insert(tk.END, f"Prev Hash: {block['prev_hash']}\n")
        text_area.insert(tk.END, f"Hash: {block['hash']}\n")
        text_area.insert(tk.END, "-"*50 + "\n")

# Verify blockchain
def verify_chain():
    for i in range(1, len(blockchain)):
        if blockchain[i]['prev_hash'] != blockchain[i-1]['hash']:
            messagebox.showerror("Error", "Blockchain is Tampered ❌")
            return
    messagebox.showinfo("Success", "Blockchain is Secure ✅")

# UI setup
root = tk.Tk()
root.title("Secure Decentralized Storage - Blockchain UI")
root.geometry("700x500")

# Input
tk.Label(root, text="Enter Data:", font=("Arial", 12)).pack(pady=5)
entry = tk.Entry(root, width=50)
entry.pack(pady=5)

# Buttons
tk.Button(root, text="Add Block", command=add_block, bg="green", fg="white").pack(pady=5)
tk.Button(root, text="Verify Blockchain", command=verify_chain, bg="blue", fg="white").pack(pady=5)

# Display area
text_area = scrolledtext.ScrolledText(root, width=80, height=20)
text_area.pack(pady=10)

root.mainloop()

def tamper_block():
    if blockchain:
        blockchain[0]['data'] = "HACKED DATA"
        display_chain()