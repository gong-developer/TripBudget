// Return integer KRW, or null for unsupported or out-of-range input.
export function parseBudget(input) {
  const text = input.replace(/\s+/g, '');
  const match = text.match(/^((?:\d+|\d{1,3}(?:,\d{3})+))(?:\.(\d{1,4}))?(만)?(?:원)?$/);
  if (!match || (match[2] && !match[3])) return null;
  const whole = Number(match[1].replaceAll(',', ''));
  const amount = match[3]
    ? whole * 10000 + Number((match[2] || '').padEnd(4, '0'))
    : whole;
  return Number.isSafeInteger(amount) && amount >= 1 && amount <= 100000000 ? amount : null;
}
