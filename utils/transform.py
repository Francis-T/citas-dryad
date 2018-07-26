import struct

## data value conversions
class DataTransformation():
    def unpack_U16(self, val):
        return float(struct.unpack("<H", val)[0])

    def decode_float32(self, val):
        return struct.unpack('f', val)[0]

    def conv_ph(self, adc_val):
        offset = 1
        val = (adc_val * 5.0) / 1024 / 6
        return val * 3.5 + offset

    def conv_batt(self, adc_val):
        max_batt = 4.87
        val = 2 * adc_val * max_batt / (997.376)
        return val

    def conv_temp(self, val):
        return val

    def conv_ec(self, val):
        if val == 0.0:
            return 0.0

        if val > 1771:
            return 10.0
        dec_val = (val / 1771.0) * 10.0
        return dec_val

    def conv_humidity(self, val):
        return val

    def conv_light(self, val):
        if val == 0.0:
            return 0.0

        dec_val = 16655.6019 * pow(val, -1.0606619)
        return dec_val

    def conv_moisture(self, val):
        return val

    def conv_mac(self, ref_addr):
        out_addr = ""
        pairs = []
        idx = 0

        pair = ""
        for idx in range(0, len(ref_addr)):
            if ((idx % 2) == 0):
                pair = ref_addr[idx]
            else:
                pair += ref_addr[idx]
                pairs.append(pair)

        out_addr = ":".join(pairs)
        return out_addr


