import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import game


class Digging(unittest.TestCase):
    def test_a_new_game_starts_with_no_gold(self):
        self.assertEqual(game.new_game()["gold"], 0)

    def test_a_dig_with_the_wood_pick_finds_one_gold(self):
        s = game.new_game()
        self.assertEqual(game.dig(s, luck=0.5), 1)
        self.assertEqual(s["gold"], 1)

    def test_a_lucky_dig_finds_double(self):
        s = game.new_game()
        self.assertEqual(game.dig(s, luck=0.01), 2)

    def test_every_dig_is_counted(self):
        s = game.new_game()
        for _ in range(5):
            game.dig(s, luck=0.5)
        self.assertEqual(s["digs"], 5)


class Shop(unittest.TestCase):
    def test_a_pick_costs_its_price_in_gold(self):
        s = dict(game.new_game(), gold=25)
        self.assertTrue(game.buy(s, "iron"))
        self.assertEqual(s["gold"], 5)

    def test_you_cannot_buy_without_enough_gold(self):
        s = dict(game.new_game(), gold=19)
        self.assertFalse(game.buy(s, "iron"))
        self.assertEqual((s["gold"], s["pick"]), (19, "wood"))

    def test_a_better_pick_finds_more_gold(self):
        s = dict(game.new_game(), gold=20)
        game.buy(s, "iron")
        self.assertEqual(game.dig(s, luck=0.5), 3)

    def test_an_unknown_pick_is_refused(self):
        s = dict(game.new_game(), gold=999)
        self.assertFalse(game.buy(s, "diamond"))
        self.assertEqual(s["gold"], 999)


class Saving(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "save.json")

    def test_a_save_keeps_the_gold(self):
        s = dict(game.new_game(), gold=42)
        game.save(s, self.path)
        self.assertEqual(game.load(self.path)["gold"], 42)

    def test_a_save_keeps_the_pick_and_the_digs(self):
        s = dict(game.new_game(), pick="iron", digs=7)
        game.save(s, self.path)
        got = game.load(self.path)
        self.assertEqual((got["pick"], got["digs"]), ("iron", 7))

    def test_no_save_file_starts_a_new_game(self):
        self.assertEqual(game.load(self.path), game.new_game())

    def test_a_broken_save_starts_a_new_game(self):
        game.save({"gold": -5, "pick": "wood", "digs": 0}, self.path)
        self.assertEqual(game.load(self.path), game.new_game())


if __name__ == "__main__":
    unittest.main()
