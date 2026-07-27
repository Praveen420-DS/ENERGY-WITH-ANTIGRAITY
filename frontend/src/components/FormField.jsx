export default function FormField({ label, name, error, hint, unit, children, required = false }) {
    return (
        <label className={`form-field ${error ? "has-error" : ""}`} htmlFor={name}>
            <span className="field-label">{label}{required && <span aria-hidden="true"> *</span>}{unit && <span className="unit-label">{unit}</span>}</span>
            {children}
            {error ? <span className="field-error">{error}</span> : hint && <small>{hint}</small>}
        </label>
    );
}
