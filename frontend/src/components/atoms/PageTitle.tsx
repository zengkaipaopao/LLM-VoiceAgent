type PageTitleProps = {
  children: React.ReactNode;
};

export function PageTitle({ children }: PageTitleProps) {
  return <h1 className="page-title">{children}</h1>;
}
