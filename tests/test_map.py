import gc
import random
import unittest
import weakref

from immutables import Map


class HashKey:
    _crasher = None

    def __init__(self, hash, name, *, error_on_eq_to=None):
        assert hash != -1
        self.name = name
        self.hash = hash
        self.error_on_eq_to = error_on_eq_to

    def __repr__(self):
        return f'<Key name:{self.name} hash:{self.hash}>'

    def __hash__(self):
        if self._crasher is not None and self._crasher.error_on_hash:
            raise HashingError

        return self.hash

    def __eq__(self, other):
        if not isinstance(other, HashKey):
            return NotImplemented

        if self._crasher is not None and self._crasher.error_on_eq:
            raise EqError

        if self.error_on_eq_to is not None and self.error_on_eq_to is other:
            raise ValueError(f'cannot compare {self!r} to {other!r}')
        if other.error_on_eq_to is not None and other.error_on_eq_to is self:
            raise ValueError(f'cannot compare {other!r} to {self!r}')

        return (self.name, self.hash) == (other.name, other.hash)


class KeyStr(str):

    def __hash__(self):
        if HashKey._crasher is not None and HashKey._crasher.error_on_hash:
            raise HashingError
        return super().__hash__()

    def __eq__(self, other):
        if HashKey._crasher is not None and HashKey._crasher.error_on_eq:
            raise EqError
        return super().__eq__(other)


class HaskKeyCrasher:

    def __init__(self, *, error_on_hash=False, error_on_eq=False):
        self.error_on_hash = error_on_hash
        self.error_on_eq = error_on_eq

    def __enter__(self):
        if HashKey._crasher is not None:
            raise RuntimeError('cannot nest crashers')
        HashKey._crasher = self

    def __exit__(self, *exc):
        HashKey._crasher = None


class HashingError(Exception):
    pass


class EqError(Exception):
    pass


class MapTest(unittest.TestCase):

    def test_hashkey_helper_1(self):
        k1 = HashKey(10, 'aaa')
        k2 = HashKey(10, 'bbb')

        self.assertNotEqual(k1, k2)
        self.assertEqual(hash(k1), hash(k2))

        d = dict()
        d[k1] = 'a'
        d[k2] = 'b'

        self.assertEqual(d[k1], 'a')
        self.assertEqual(d[k2], 'b')

    def test_map_basics_1(self):
        h = Map()
        h = None  # NoQA

    def test_map_basics_2(self):
        h = Map()
        self.assertEqual(len(h), 0)

        h2 = h.set('a', 'b')
        self.assertIsNot(h, h2)
        self.assertEqual(len(h), 0)
        self.assertEqual(len(h2), 1)

        self.assertIsNone(h.get('a'))
        self.assertEqual(h.get('a', 42), 42)

        self.assertEqual(h2.get('a'), 'b')

        h3 = h2.set('b', 10)
        self.assertIsNot(h2, h3)
        self.assertEqual(len(h), 0)
        self.assertEqual(len(h2), 1)
        self.assertEqual(len(h3), 2)
        self.assertEqual(h3.get('a'), 'b')
        self.assertEqual(h3.get('b'), 10)

        self.assertIsNone(h.get('b'))
        self.assertIsNone(h2.get('b'))

        self.assertIsNone(h.get('a'))
        self.assertEqual(h2.get('a'), 'b')

        h = h2 = h3 = None

    def test_map_basics_3(self):
        h = Map()
        o = object()
        h1 = h.set('1', o)
        h2 = h1.set('1', o)
        self.assertIs(h1, h2)

    def test_map_basics_4(self):
        h = Map()
        h1 = h.set('key', [])
        h2 = h1.set('key', [])
        self.assertIsNot(h1, h2)
        self.assertEqual(len(h1), 1)
        self.assertEqual(len(h2), 1)
        self.assertIsNot(h1.get('key'), h2.get('key'))

    def test_map_collision_1(self):
        k1 = HashKey(10, 'aaa')
        k2 = HashKey(10, 'bbb')
        k3 = HashKey(10, 'ccc')

        h = Map()
        h2 = h.set(k1, 'a')
        h3 = h2.set(k2, 'b')

        self.assertEqual(h.get(k1), None)
        self.assertEqual(h.get(k2), None)

        self.assertEqual(h2.get(k1), 'a')
        self.assertEqual(h2.get(k2), None)

        self.assertEqual(h3.get(k1), 'a')
        self.assertEqual(h3.get(k2), 'b')

        h4 = h3.set(k2, 'cc')
        h5 = h4.set(k3, 'aa')

        self.assertEqual(h3.get(k1), 'a')
        self.assertEqual(h3.get(k2), 'b')
        self.assertEqual(h4.get(k1), 'a')
        self.assertEqual(h4.get(k2), 'cc')
        self.assertEqual(h4.get(k3), None)
        self.assertEqual(h5.get(k1), 'a')
        self.assertEqual(h5.get(k2), 'cc')
        self.assertEqual(h5.get(k2), 'cc')
        self.assertEqual(h5.get(k3), 'aa')

        self.assertEqual(len(h), 0)
        self.assertEqual(len(h2), 1)
        self.assertEqual(len(h3), 2)
        self.assertEqual(len(h4), 2)
        self.assertEqual(len(h5), 3)

    def test_map_stress(self):
        COLLECTION_SIZE = 7000
        TEST_ITERS_EVERY = 647
        CRASH_HASH_EVERY = 97
        CRASH_EQ_EVERY = 11
        RUN_XTIMES = 3

        for _ in range(RUN_XTIMES):
            h = Map()
            d = dict()

            for i in range(COLLECTION_SIZE):
                key = KeyStr(i)

                if not (i % CRASH_HASH_EVERY):
                    with HaskKeyCrasher(error_on_hash=True):
                        with self.assertRaises(HashingError):
                            h.set(key, i)

                h = h.set(key, i)

                if not (i % CRASH_EQ_EVERY):
                    with HaskKeyCrasher(error_on_eq=True):
                        with self.assertRaises(EqError):
                            h.get(KeyStr(i))  # really trigger __eq__

                d[key] = i
                self.assertEqual(len(d), len(h))

                if not (i % TEST_ITERS_EVERY):
                    self.assertEqual(set(h.items()), set(d.items()))
                    self.assertEqual(len(h.items()), len(d.items()))

            self.assertEqual(len(h), COLLECTION_SIZE)

            for key in range(COLLECTION_SIZE):
                self.assertEqual(h.get(KeyStr(key), 'not found'), key)

            keys_to_delete = list(range(COLLECTION_SIZE))
            random.shuffle(keys_to_delete)
            for iter_i, i in enumerate(keys_to_delete):
                key = KeyStr(i)

                if not (iter_i % CRASH_HASH_EVERY):
                    with HaskKeyCrasher(error_on_hash=True):
                        with self.assertRaises(HashingError):
                            h.delete(key)

                if not (iter_i % CRASH_EQ_EVERY):
                    with HaskKeyCrasher(error_on_eq=True):
                        with self.assertRaises(EqError):
                            h.delete(KeyStr(i))

                h = h.delete(key)
                self.assertEqual(h.get(key, 'not found'), 'not found')
                del d[key]
                self.assertEqual(len(d), len(h))

                if iter_i == COLLECTION_SIZE // 2:
                    hm = h
                    dm = d.copy()

                if not (iter_i % TEST_ITERS_EVERY):
                    self.assertEqual(set(h.keys()), set(d.keys()))
                    self.assertEqual(len(h.keys()), len(d.keys()))

            self.assertEqual(len(d), 0)
            self.assertEqual(len(h), 0)

            # ============

            for key in dm:
                self.assertEqual(hm.get(str(key)), dm[key])
            self.assertEqual(len(dm), len(hm))

            for i, key in enumerate(keys_to_delete):
                hm = hm.delete(str(key))
                self.assertEqual(hm.get(str(key), 'not found'), 'not found')
                dm.pop(str(key), None)
                self.assertEqual(len(d), len(h))

                if not (i % TEST_ITERS_EVERY):
                    self.assertEqual(set(h.values()), set(d.values()))
                    self.assertEqual(len(h.values()), len(d.values()))

            self.assertEqual(len(d), 0)
            self.assertEqual(len(h), 0)
            self.assertEqual(list(h.items()), [])

    def test_map_delete_1(self):
        A = HashKey(100, 'A')
        B = HashKey(101, 'B')
        C = HashKey(102, 'C')
        D = HashKey(103, 'D')
        E = HashKey(104, 'E')
        Z = HashKey(-100, 'Z')

        Er = HashKey(103, 'Er', error_on_eq_to=D)

        h = Map()
        h = h.set(A, 'a')
        h = h.set(B, 'b')
        h = h.set(C, 'c')
        h = h.set(D, 'd')
        h = h.set(E, 'e')

        orig_len = len(h)

        # BitmapNode(size=10 bitmap=0b111110000 id=0x10eadc618):
        #     <Key name:A hash:100>: 'a'
        #     <Key name:B hash:101>: 'b'
        #     <Key name:C hash:102>: 'c'
        #     <Key name:D hash:103>: 'd'
        #     <Key name:E hash:104>: 'e'

        h = h.delete(C)
        self.assertEqual(len(h), orig_len - 1)

        with self.assertRaisesRegex(ValueError, 'cannot compare'):
            h.delete(Er)

        h = h.delete(D)
        self.assertEqual(len(h), orig_len - 2)

        h2 = h.delete(Z)
        self.assertIs(h2, h)

        h = h.delete(A)
        self.assertEqual(len(h), orig_len - 3)

        self.assertEqual(h.get(A, 42), 42)
        self.assertEqual(h.get(B), 'b')
        self.assertEqual(h.get(E), 'e')

    def test_map_delete_2(self):
        A = HashKey(100, 'A')
        B = HashKey(201001, 'B')
        C = HashKey(101001, 'C')
        D = HashKey(103, 'D')
        E = HashKey(104, 'E')
        Z = HashKey(-100, 'Z')

        Er = HashKey(201001, 'Er', error_on_eq_to=B)

        h = Map()
        h = h.set(A, 'a')
        h = h.set(B, 'b')
        h = h.set(C, 'c')
        h = h.set(D, 'd')
        h = h.set(E, 'e')

        orig_len = len(h)

        # BitmapNode(size=8 bitmap=0b1110010000):
        #     <Key name:A hash:100>: 'a'
        #     <Key name:D hash:103>: 'd'
        #     <Key name:E hash:104>: 'e'
        #     NULL:
        #         BitmapNode(size=4 bitmap=0b100000000001000000000):
        #             <Key name:B hash:201001>: 'b'
        #             <Key name:C hash:101001>: 'c'

        with self.assertRaisesRegex(ValueError, 'cannot compare'):
            h.delete(Er)

        h = h.delete(Z)
        self.assertEqual(len(h), orig_len)

        h = h.delete(C)
        self.assertEqual(len(h), orig_len - 1)

        h = h.delete(B)
        self.assertEqual(len(h), orig_len - 2)

        h = h.delete(A)
        self.assertEqual(len(h), orig_len - 3)

        self.assertEqual(h.get(D), 'd')
        self.assertEqual(h.get(E), 'e')

        h = h.delete(A)
        h = h.delete(B)
        h = h.delete(D)
        h = h.delete(E)
        self.assertEqual(len(h), 0)

    def test_map_delete_3(self):
        A = HashKey(100, 'A')
        B = HashKey(101, 'B')
        C = HashKey(100100, 'C')
        D = HashKey(100100, 'D')
        E = HashKey(104, 'E')

        h = Map()
        h = h.set(A, 'a')
        h = h.set(B, 'b')
        h = h.set(C, 'c')
        h = h.set(D, 'd')
        h = h.set(E, 'e')

        orig_len = len(h)

        # BitmapNode(size=6 bitmap=0b100110000):
        #     NULL:
        #         BitmapNode(size=4 bitmap=0b1000000000000000000001000):
        #             <Key name:A hash:100>: 'a'
        #             NULL:
        #                 CollisionNode(size=4 id=0x108572410):
        #                     <Key name:C hash:100100>: 'c'
        #                     <Key name:D hash:100100>: 'd'
        #     <Key name:B hash:101>: 'b'
        #     <Key name:E hash:104>: 'e'

        h = h.delete(A)
        self.assertEqual(len(h), orig_len - 1)

        h = h.delete(E)
        self.assertEqual(len(h), orig_len - 2)

        self.assertEqual(h.get(C), 'c')
        self.assertEqual(h.get(B), 'b')

    def test_map_delete_4(self):
        A = HashKey(100, 'A')
        B = HashKey(101, 'B')
        C = HashKey(100100, 'C')
        D = HashKey(100100, 'D')
        E = HashKey(100100, 'E')

        h = Map()
        h = h.set(A, 'a')
        h = h.set(B, 'b')
        h = h.set(C, 'c')
        h = h.set(D, 'd')
        h = h.set(E, 'e')

        orig_len = len(h)

        # BitmapNode(size=4 bitmap=0b110000):
        #     NULL:
        #         BitmapNode(size=4 bitmap=0b1000000000000000000001000):
        #             <Key name:A hash:100>: 'a'
        #             NULL:
        #                 CollisionNode(size=6 id=0x10515ef30):
        #                     <Key name:C hash:100100>: 'c'
        #                     <Key name:D hash:100100>: 'd'
        #                     <Key name:E hash:100100>: 'e'
        #     <Key name:B hash:101>: 'b'

        h = h.delete(D)
        self.assertEqual(len(h), orig_len - 1)

        h = h.delete(E)
        self.assertEqual(len(h), orig_len - 2)

        h = h.delete(C)
        self.assertEqual(len(h), orig_len - 3)

        h = h.delete(A)
        self.assertEqual(len(h), orig_len - 4)

        h = h.delete(B)
        self.assertEqual(len(h), 0)

    def test_map_delete_5(self):
        h = Map()

        keys = []
        for i in range(17):
            key = HashKey(i, str(i))
            keys.append(key)
            h = h.set(key, f'val-{i}')

        collision_key16 = HashKey(16, '18')
        h = h.set(collision_key16, 'collision')

        # ArrayNode(id=0x10f8b9318):
        #     0::
        #     BitmapNode(size=2 count=1 bitmap=0b1):
        #         <Key name:0 hash:0>: 'val-0'
        #
        # ... 14 more BitmapNodes ...
        #
        #     15::
        #     BitmapNode(size=2 count=1 bitmap=0b1):
        #         <Key name:15 hash:15>: 'val-15'
        #
        #     16::
        #     BitmapNode(size=2 count=1 bitmap=0b1):
        #         NULL:
        #             CollisionNode(size=4 id=0x10f2f5af8):
        #                 <Key name:16 hash:16>: 'val-16'
        #                 <Key name:18 hash:16>: 'collision'

        self.assertEqual(len(h), 18)

        h = h.delete(keys[2])
        self.assertEqual(len(h), 17)

        h = h.delete(collision_key16)
        self.assertEqual(len(h), 16)
        h = h.delete(keys[16])
        self.assertEqual(len(h), 15)

        h = h.delete(keys[1])
        self.assertEqual(len(h), 14)
        h = h.delete(keys[1])
        self.assertEqual(len(h), 14)

        for key in keys:
            h = h.delete(key)
        self.assertEqual(len(h), 0)

    def test_map_items_1(self):
        A = HashKey(100, 'A')
        B = HashKey(201001, 'B')
        C = HashKey(101001, 'C')
        D = HashKey(103, 'D')
        E = HashKey(104, 'E')
        F = HashKey(110, 'F')

        h = Map()
        h = h.set(A, 'a')
        h = h.set(B, 'b')
        h = h.set(C, 'c')
        h = h.set(D, 'd')
        h = h.set(E, 'e')
        h = h.set(F, 'f')

        it = h.items()
        self.assertEqual(
            set(list(it)),
            {(A, 'a'), (B, 'b'), (C, 'c'), (D, 'd'), (E, 'e'), (F, 'f')})

    def test_map_items_2(self):
        A = HashKey(100, 'A')
        B = HashKey(101, 'B')
        C = HashKey(100100, 'C')
        D = HashKey(100100, 'D')
        E = HashKey(100100, 'E')
        F = HashKey(110, 'F')

        h = Map()
        h = h.set(A, 'a')
        h = h.set(B, 'b')
        h = h.set(C, 'c')
        h = h.set(D, 'd')
        h = h.set(E, 'e')
        h = h.set(F, 'f')

        it = h.items()
        self.assertEqual(
            set(list(it)),
            {(A, 'a'), (B, 'b'), (C, 'c'), (D, 'd'), (E, 'e'), (F, 'f')})

    def test_map_keys_1(self):
        A = HashKey(100, 'A')
        B = HashKey(101, 'B')
        C = HashKey(100100, 'C')
        D = HashKey(100100, 'D')
        E = HashKey(100100, 'E')
        F = HashKey(110, 'F')

        h = Map()
        h = h.set(A, 'a')
        h = h.set(B, 'b')
        h = h.set(C, 'c')
        h = h.set(D, 'd')
        h = h.set(E, 'e')
        h = h.set(F, 'f')

        self.assertEqual(set(list(h.keys())), {A, B, C, D, E, F})
        self.assertEqual(set(list(h)), {A, B, C, D, E, F})

    def test_map_items_3(self):
        h = Map()
        self.assertEqual(len(h.items()), 0)
        self.assertEqual(list(h.items()), [])

    def test_map_eq_1(self):
        A = HashKey(100, 'A')
        B = HashKey(101, 'B')
        C = HashKey(100100, 'C')
        D = HashKey(100100, 'D')
        E = HashKey(120, 'E')

        h1 = Map()
        h1 = h1.set(A, 'a')
        h1 = h1.set(B, 'b')
        h1 = h1.set(C, 'c')
        h1 = h1.set(D, 'd')

        h2 = Map()
        h2 = h2.set(A, 'a')

        self.assertFalse(h1 == h2)
        self.assertTrue(h1 != h2)

        h2 = h2.set(B, 'b')
        self.assertFalse(h1 == h2)
        self.assertTrue(h1 != h2)

        h2 = h2.set(C, 'c')
        self.assertFalse(h1 == h2)
        self.assertTrue(h1 != h2)

        h2 = h2.set(D, 'd2')
        self.assertFalse(h1 == h2)
        self.assertTrue(h1 != h2)

        h2 = h2.set(D, 'd')
        self.assertTrue(h1 == h2)
        self.assertFalse(h1 != h2)

        h2 = h2.set(E, 'e')
        self.assertFalse(h1 == h2)
        self.assertTrue(h1 != h2)

        h2 = h2.delete(D)
        self.assertFalse(h1 == h2)
        self.assertTrue(h1 != h2)

        h2 = h2.set(E, 'd')
        self.assertFalse(h1 == h2)
        self.assertTrue(h1 != h2)

    def test_map_eq_2(self):
        A = HashKey(100, 'A')
        Er = HashKey(100, 'Er', error_on_eq_to=A)

        h1 = Map()
        h1 = h1.set(A, 'a')

        h2 = Map()
        h2 = h2.set(Er, 'a')

        with self.assertRaisesRegex(ValueError, 'cannot compare'):
            h1 == h2

        with self.assertRaisesRegex(ValueError, 'cannot compare'):
            h1 != h2

    def test_map_gc_1(self):
        A = HashKey(100, 'A')

        h = Map()
        h = h.set(0, 0)  # empty Map node is memoized in _map.c
        ref = weakref.ref(h)

        a = []
        a.append(a)
        a.append(h)
        b = []
        a.append(b)
        b.append(a)
        h = h.set(A, b)

        del h, a, b

        gc.collect()
        gc.collect()
        gc.collect()

        self.assertIsNone(ref())

    def test_map_gc_2(self):
        A = HashKey(100, 'A')

        h = Map()
        h = h.set(A, 'a')
        h = h.set(A, h)

        ref = weakref.ref(h)
        hi = h.items()
        next(hi)

        del h, hi

        gc.collect()
        gc.collect()
        gc.collect()

        self.assertIsNone(ref())

    def test_map_in_1(self):
        A = HashKey(100, 'A')
        AA = HashKey(100, 'A')

        B = HashKey(101, 'B')

        h = Map()
        h = h.set(A, 1)

        self.assertTrue(A in h)
        self.assertFalse(B in h)

        with self.assertRaises(EqError):
            with HaskKeyCrasher(error_on_eq=True):
                AA in h

        with self.assertRaises(HashingError):
            with HaskKeyCrasher(error_on_hash=True):
                AA in h

    def test_map_getitem_1(self):
        A = HashKey(100, 'A')
        AA = HashKey(100, 'A')

        B = HashKey(101, 'B')

        h = Map()
        h = h.set(A, 1)

        self.assertEqual(h[A], 1)
        self.assertEqual(h[AA], 1)

        with self.assertRaises(KeyError):
            h[B]

        with self.assertRaises(EqError):
            with HaskKeyCrasher(error_on_eq=True):
                h[AA]

        with self.assertRaises(HashingError):
            with HaskKeyCrasher(error_on_hash=True):
                h[AA]


if __name__ == "__main__":
    unittest.main()