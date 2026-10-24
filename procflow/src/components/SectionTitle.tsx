type SectionTitleProps = {
  eyebrow: string;
  title: string;
  description: string;
  id?: string;
};

export function SectionTitle({ eyebrow, title, description, id }: SectionTitleProps) {
  return (
    <div className="section-title">
      <p className="eyebrow">{eyebrow}</p>
      <h2 id={id}>{title}</h2>
      <p className="section-title__description">{description}</p>
    </div>
  );
}
