export default function StatCard({ title, value, subtitle, icon: Icon, tone = "purple" }) {
    return <article className="stat-card"><div className={`stat-icon ${tone}`}>{Icon && <Icon size={21} />}</div><div className="stat-copy"><p>{title}</p><h2>{value}</h2><span>{subtitle}</span></div></article>;
}
