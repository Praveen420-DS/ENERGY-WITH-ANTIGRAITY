import { X } from "lucide-react";
import { useEffect } from "react";

export default function Modal({ open, title, children, onClose }) {
    useEffect(() => {
        if (!open) return undefined;
        const close = (event) => event.key === "Escape" && onClose();
        window.addEventListener("keydown", close);
        return () => window.removeEventListener("keydown", close);
    }, [open, onClose]);
    if (!open) return null;
    return <div className="modal-backdrop" onMouseDown={onClose}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" onMouseDown={(event) => event.stopPropagation()}><div className="modal-header"><h2 id="modal-title">{title}</h2><button onClick={onClose} aria-label="Close modal"><X /></button></div>{children}</section></div>;
}
