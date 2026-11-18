import test from 'node:test';
import assert from 'node:assert/strict';
import { parseAddress } from './addressParser.ts';

test('parseAddress: pure 5-digit zip', () => {
  assert.deepEqual(parseAddress('90007'), {
    street: '',
    city: '',
    state: '',
    zipCode: '90007',
  });
  assert.deepEqual(parseAddress('  90007  '), {
    street: '',
    city: '',
    state: '',
    zipCode: '90007',
  });
});

test('parseAddress: pure 9-digit zip', () => {
  assert.deepEqual(parseAddress('90007-1234'), {
    street: '',
    city: '',
    state: '',
    zipCode: '90007-1234',
  });
  assert.deepEqual(parseAddress('900071234'), {
    street: '',
    city: '',
    state: '',
    zipCode: '90007-1234',
  });
});

test('parseAddress: full address with commas', () => {
  assert.deepEqual(parseAddress('123 Main St, Los Angeles, CA 90007'), {
    street: '123 Main St',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '90007',
  });

  assert.deepEqual(parseAddress('123 Main St, Los Angeles, CA 90007-1234'), {
    street: '123 Main St',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '90007-1234',
  });

  assert.deepEqual(parseAddress('123 Main St, Los Angeles, CA, 90007'), {
    street: '123 Main St',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '90007',
  });
});

test('parseAddress: address with unit/apt', () => {
  assert.deepEqual(parseAddress('123 Main St, Apt 4B, Los Angeles, CA 90007'), {
    street: '123 Main St, Apt 4B',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '90007',
  });
});

test('parseAddress: full state name', () => {
  assert.deepEqual(parseAddress('123 Main St, Los Angeles, California 90007'), {
    street: '123 Main St',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '90007',
  });
});

test('parseAddress: address without commas', () => {
  assert.deepEqual(parseAddress('123 Main St Los Angeles CA 90007'), {
    street: '123 Main St',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '90007',
  });
});

test('parseAddress: city and state and zip without street', () => {
  assert.deepEqual(parseAddress('Los Angeles, CA 90007'), {
    street: '',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '90007',
  });

  assert.deepEqual(parseAddress('Los Angeles CA 90007'), {
    street: '',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '90007',
  });
});

test('parseAddress: street and zip without city/state', () => {
  assert.deepEqual(parseAddress('123 Main St, 90007'), {
    street: '123 Main St',
    city: '',
    state: '',
    zipCode: '90007',
  });
});

test('parseAddress: object input passed through', () => {
  assert.deepEqual(
    parseAddress({
      street: '456 Oak St',
      city: 'Portland',
      state: 'OR',
      zipCode: '97201',
    }),
    {
      street: '456 Oak St',
      city: 'Portland',
      state: 'OR',
      zipCode: '97201',
    }
  );
});

test('parseAddress: PO Box address', () => {
  assert.deepEqual(parseAddress('P.O. Box 123, Seattle, WA 98101'), {
    street: 'P.O. Box 123',
    city: 'Seattle',
    state: 'WA',
    zipCode: '98101',
  });
});

test('parseAddress: suite with comma', () => {
  assert.deepEqual(parseAddress('500 5th Ave, Suite 1200, New York, NY 10110'), {
    street: '500 5th Ave, Suite 1200',
    city: 'New York',
    state: 'NY',
    zipCode: '10110',
  });
});

test('parseAddress: street, city, state without zip', () => {
  assert.deepEqual(parseAddress('123 Main St, Los Angeles, CA'), {
    street: '123 Main St',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '',
  });

  assert.deepEqual(parseAddress('123 Main St Los Angeles CA'), {
    street: '123 Main St',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '',
  });

  assert.deepEqual(parseAddress('123 Main St, Los Angeles, California'), {
    street: '123 Main St',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '',
  });

  assert.deepEqual(parseAddress('Los Angeles, CA'), {
    street: '',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '',
  });
});

test('parseAddress: coordinates string and object', () => {
  assert.deepEqual(parseAddress('34.0522, -118.2437'), {
    street: '',
    city: '',
    state: '',
    zipCode: '',
    latitude: 34.0522,
    longitude: -118.2437,
  });

  assert.deepEqual(
    parseAddress({
      street: '',
      city: '',
      state: '',
      zipCode: '',
      latitude: 34.0522,
      longitude: -118.2437,
    }),
    {
      street: '',
      city: '',
      state: '',
      zipCode: '',
      latitude: 34.0522,
      longitude: -118.2437,
    }
  );
});

test('parseAddress: empty or whitespace', () => {
  assert.deepEqual(parseAddress(''), {
    street: '',
    city: '',
    state: '',
    zipCode: '',
  });
  assert.deepEqual(parseAddress('   '), {
    street: '',
    city: '',
    state: '',
    zipCode: '',
  });
});
