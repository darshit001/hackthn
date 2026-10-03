import { Icon } from "../Icon";

// community (with its caption colour), language and length (a ready video shows its real one on the thumbnail), plus any extra facts a card wants to add
export function Facts({ job, label, accent, length = true, children }) {
  return (
    <ul className="facts">
      <li><i className="swatch" style={{ background: accent }} aria-hidden="true" />{label(job.community)}</li>
      <li><Icon name="languages" />{label(job.language)}</li>
      {length && <li><Icon name="clock" />{job.duration} s</li>}
      {children}
    </ul>
  );
}
