
# Is it an Asian character?
def is_jpc(char):
    # Ox3000 is ideographic space (i.e. double-byte space)
    # Anything over is an Asian character
    IDEOGRAPHIC_SPACE = 0x3000
    return ord(char) > IDEOGRAPHIC_SPACE


def count_JPC(string: str):
    converted = string.replace("\r","")
    converted = converted.replace("\n","")
    return len(converted)
