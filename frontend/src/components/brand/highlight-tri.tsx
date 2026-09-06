type HighlightTriProps = {
  prefix: string;
  rest: string;
};

export function HighlightTri({ prefix, rest }: HighlightTriProps) {
  return (
    <span>
      <span className="inline-block bg-gradient-to-b from-brand-gold to-brand-green bg-clip-text text-transparent">
        {prefix}
      </span>
      {rest}
    </span>
  );
}
