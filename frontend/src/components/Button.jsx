import { LoaderCircle } from "lucide-react";

export default function Button({ children, variant = "primary", loading = false, icon: Icon, className = "", ...props }) {
    return (
        <button className={`button button-${variant} ${className}`} disabled={loading || props.disabled} {...props}>
            {loading ? <LoaderCircle className="spin" size={17} /> : Icon ? <Icon size={17} /> : null}
            <span>{children}</span>
        </button>
    );
}
