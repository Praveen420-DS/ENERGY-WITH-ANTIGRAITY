import { LoaderCircle } from "lucide-react";

export default function LoadingSpinner({ label = "Loading data…" }) {
    return <div className="loading-state" role="status"><LoaderCircle className="spin" /><span>{label}</span></div>;
}
