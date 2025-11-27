type PageSubtitleProps = {
  children: React.ReactNode;
};

export function PageSubtitle({ children }: PageSubtitleProps) {
  return <p className="page-subtitle">{children}</p>;
}
