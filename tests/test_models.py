import pyrsistent as pr

from daquiri.reactive_utils import RxListPattern, Transaction


class Sink:
    value = None

    def receive(self, v):
        self.value = v


def test_rx_list_model(qtmodeltester):
    s = Sink()
    pattern = RxListPattern()
    pattern.values.subscribe(s.receive)
    model = pattern.bind_to_model()

    pattern.add.on_next(Transaction.add(new_value="a"))
    qtmodeltester.check(model)
    pattern.add.on_next(Transaction.add(new_value="b"))
    qtmodeltester.check(model)
    pattern.add.on_next(Transaction.add(new_value="c"))
    qtmodeltester.check(model)
    pattern.add.on_next(Transaction.add(1, new_value="ins"))
    qtmodeltester.check(model)
    pattern.remove.on_next(Transaction.remove(0))
    qtmodeltester.check(model)

    assert s.value == pr.v("ins", "b", "c")
