import test from 'node:test';
import assert from 'node:assert/strict';
import { parseBudget } from '../src/budget.js';

test('parses won, man-won, decimals and whitespace as integer KRW', () => {
  for (const [input, expected] of [
    ['500만원',5000000], ['500만',5000000], ['1.5만원',15000],
    ['5000000',5000000], ['5,000,000원',5000000], [' 500 만 원 ',5000000],
    ['0.0001만',1], ['1원',1], ['10,000만원',100000000],
    ['100000000',100000000], ['1.2345만원',12345],
  ]) assert.equal(parseBudget(input), expected, input);
});

test('rejects malformed, fractional-won and out-of-range budgets', () => {
  for (const input of ['', '원', '만', '0', '-500만', '1.5원', '1.5',
    '50,00원', '500만원원', '500만abc', '1e6', 'Infinity', '1억',
    '10001만원', '100000001', '0.00001만원', '9007199254740993', '+500']) {
    assert.equal(parseBudget(input), null, input);
  }
});
