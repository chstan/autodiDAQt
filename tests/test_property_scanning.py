from daquiri.experiment import ScopedAccessRecorder
from daquiri.scan import scan
from .common import PropertyInstrument, MockExperiment

dsensitivity = PropertyInstrument.scan('ins').sensitivity()
dtime_constant = PropertyInstrument.scan('ins').time_constant()
dcat = PropertyInstrument.scan('ins').categorical()


def test_scan_property_elements():
    fields = dsensitivity.to_fields(base_name='test')
    assert [x[0] for x in fields] == ['start_test', 'stop_test']
    assert [v.value for v in fields[0][1].__members__.values()] == list(range(1, 29))
    assert [v for v in fields[0][1].__members__.keys()][:5] == ['0 V', '1 V', '2 V', '3 V', '4 V', ]

    fields = dcat.to_fields(base_name='test2')
    assert [x[0] for x in fields] == ['start_test2', 'stop_test2']
    assert [v.value for v in fields[0][1].__members__.values()] == [1, 2, 3, 4, 5]
    assert [v for v in fields[0][1].__members__.keys()] == ['A', 'B', 'C', 'D', 'E']


def test_scan_property(app):
    test_scan = scan(sensitivity=dsensitivity, categorical=dcat, name='Test Scan')
    scan_instance = test_scan()

    scan_instance.start_sensitivity = 1
    scan_instance.stop_sensitivity = 1

    scan_instance.start_categorical = 2
    scan_instance.stop_categorical = 3

    seq = list(scan_instance.sequence(
        experiment=MockExperiment(), ins=ScopedAccessRecorder('ins')))
    assert len(seq) == 4

    def extract(daq_sequence):
        processed_items = []
        for daq_item in daq_sequence:
            item = []
            for element in daq_item:
                item.append(element['set'])

            processed_items.append(item)

        return processed_items

    assert extract(seq) == extract([
        [{'set': 0.0, 'path': ['sensitivity'], 'scope': 'ins'},
         {'set': 'B', 'path': ['categorical'], 'scope': 'ins'}],
        [], # no reads
        [{'set': 0.0, 'path': ['sensitivity'], 'scope': 'ins'},
         {'set': 'C', 'path': ['categorical'], 'scope': 'ins'}],
        [],
    ])

    scan_instance.start_sensitivity = 1
    scan_instance.stop_sensitivity = 5

    scan_instance.start_categorical = 2
    scan_instance.stop_categorical = 5

    seq = list(scan_instance.sequence(
        experiment=MockExperiment(), ins=ScopedAccessRecorder('ins')))
    assert len(seq) == (5 * 4) * 2
