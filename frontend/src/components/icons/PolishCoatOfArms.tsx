interface CoatOfArmsProps {
  className?: string;
}

export function PolishCoatOfArms({ className = "h-10 w-auto" }: CoatOfArmsProps) {
  return (
    <img
      src="/godlo-polski.svg"
      alt="Godło Rzeczypospolitej Polskiej"
      className={`coat-of-arms object-contain select-none ${className}`}
    />
  );
}
