import unittest
import numpy as np
from audit import components, diamond_center


class MarkerConnectivity(unittest.TestCase):
    def diamond(self):
        y, x = np.indices((15, 15))
        return abs(x - 7) + abs(y - 7) <= 2

    def test_disconnected_diamond(self):
        _, groups = components(self.diamond())
        self.assertEqual([diamond_center(p) for p in groups], [(7, 7)])

    def test_attached_curve_is_rejected(self):
        mask = self.diamond()
        mask[7, 9:14] = True
        _, groups = components(mask)
        self.assertEqual([diamond_center(p) for p in groups], [None])

    def test_diagonal_contact_is_rejected(self):
        mask = self.diamond()
        mask[8, 10] = True
        _, groups = components(mask)
        self.assertEqual([diamond_center(p) for p in groups], [None])

    def test_wrong_shape_with_same_count_is_rejected(self):
        pixels = np.column_stack([np.zeros(13, int), np.arange(13)])
        self.assertIsNone(diamond_center(pixels))


if __name__ == '__main__':
    unittest.main()
