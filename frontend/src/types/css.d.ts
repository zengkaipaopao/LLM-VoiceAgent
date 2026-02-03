declare module '*.module.css' {
  const classes: { [key: string]: string };
  export default classes;
}

declare module '*.module.scss' {
  const scssClasses: { [key: string]: string };
  export default scssClasses;
}
