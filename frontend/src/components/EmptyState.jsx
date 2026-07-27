import { Inbox } from "lucide-react";

export default function EmptyState({ icon: Icon = Inbox, title, description, action }) {
    return <div className="empty-state"><span className="empty-icon"><Icon size={25} /></span><h3>{title}</h3><p>{description}</p>{action}</div>;
}
