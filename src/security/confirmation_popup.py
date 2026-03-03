"""Native Windows confirmation popup for dangerous actions."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class ConfirmationResult:
    action: str  # "allow", "deny", "timeout"
    deny_reason: str | None = None

    @property
    def is_allowed(self) -> bool:
        return self.action == "allow"


def build_description(tool_name: str, parameters: dict[str, Any]) -> str:
    """Format tool details for display in the confirmation popup."""
    lines = [f"Tool: {tool_name}", "", "Parameters:"]
    for key, value in parameters.items():
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def show_confirmation(
    tool_name: str,
    parameters: dict[str, Any],
    timeout_seconds: int = 60,
) -> ConfirmationResult:
    """Show a native Windows confirmation popup. Blocks until user responds or timeout."""
    result_holder: list[ConfirmationResult] = []

    def _run_popup():
        try:
            import customtkinter as ctk
        except ImportError:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            desc = build_description(tool_name, parameters)
            answer = messagebox.askyesno("Action Requires Approval", desc)
            root.destroy()
            if answer:
                result_holder.append(ConfirmationResult(action="allow"))
            else:
                result_holder.append(ConfirmationResult(action="deny"))
            return

        ctk.set_appearance_mode("dark")

        app = ctk.CTkToplevel()
        app.title("Action Requires Approval")
        app.geometry("500x400")
        app.attributes("-topmost", True)
        app.resizable(False, False)

        remaining = [timeout_seconds]

        title_label = ctk.CTkLabel(
            app, text="Warning: Action Requires Approval",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        title_label.pack(pady=(15, 5))

        countdown_label = ctk.CTkLabel(
            app, text=f"Auto-deny in {remaining[0]}s",
            font=ctk.CTkFont(size=12),
            text_color="orange",
        )
        countdown_label.pack(pady=(0, 10))

        desc = build_description(tool_name, parameters)
        details_box = ctk.CTkTextbox(app, width=460, height=150)
        details_box.pack(padx=20, pady=5)
        details_box.insert("1.0", desc)
        details_box.configure(state="disabled")

        reason_frame = ctk.CTkFrame(app)
        reason_entry = ctk.CTkEntry(reason_frame, placeholder_text="Enter reason...", width=360)

        def on_allow():
            result_holder.append(ConfirmationResult(action="allow"))
            app.destroy()

        def on_deny():
            result_holder.append(ConfirmationResult(action="deny"))
            app.destroy()

        def on_deny_with_reason():
            reason_frame.pack(pady=5)
            reason_entry.pack(side="left", padx=(10, 5))
            submit_btn = ctk.CTkButton(
                reason_frame, text="Submit", width=80,
                command=lambda: _submit_reason(),
            )
            submit_btn.pack(side="left")

        def _submit_reason():
            reason = reason_entry.get().strip() or "No reason given"
            result_holder.append(ConfirmationResult(action="deny", deny_reason=reason))
            app.destroy()

        btn_frame = ctk.CTkFrame(app, fg_color="transparent")
        btn_frame.pack(pady=15)

        ctk.CTkButton(btn_frame, text="Allow", fg_color="green", width=120, command=on_allow).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Deny", fg_color="red", width=120, command=on_deny).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Deny with Reason", width=140, command=on_deny_with_reason).pack(side="left", padx=5)

        def tick():
            remaining[0] -= 1
            if remaining[0] <= 0:
                result_holder.append(ConfirmationResult(action="timeout"))
                app.destroy()
                return
            countdown_label.configure(text=f"Auto-deny in {remaining[0]}s")
            app.after(1000, tick)

        app.after(1000, tick)
        app.mainloop()

    thread = threading.Thread(target=_run_popup, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds + 5)

    if result_holder:
        return result_holder[0]
    return ConfirmationResult(action="timeout")
