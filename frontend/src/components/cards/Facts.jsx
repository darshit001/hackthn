import { Icon } from "../Icon";

// community, language and length, plus any extra facts a card wants to add
export function Facts({ job, label, children }) {
  return (
    <ul className="facts">
      <li><Icon name="folder" />{label(job.community)}</li>
      <li><Icon name="languages" />{label(job.language)}</li>
      <li><Icon name="clock" />{job.duration} s</li>
      {children}
    </ul>
  );
}
