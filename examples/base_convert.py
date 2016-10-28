import math

def convert(inputString, sourceAlphabet, targetAlphabet):
    # Check that sourceAlphabet is correct
    for i in inputString:
        if i not in sourceAlphabet:
            print "Error: input string does not match with source alphabet"

    # Sets the value of the power applied to he base, starting from left hand side
    inputPower = len(inputString) - 1
    sourceBase = len(sourceAlphabet)
    targetBase = len(targetAlphabet)

    # Convert input to decimal value (used as quotient in division step)
    quotient = 0
    for i in inputString:
        quotient = quotient + (sourceAlphabet.index(i) * pow(sourceBase, inputPower))
        inputPower = inputPower - 1

    # Division step - builds the output by taking remainders as indices to target alphabet
    out = ""
    while quotient > 0:
        rem = quotient % targetBase
        # Integer division floors the result
        quotient = quotient / targetBase
        out = out + targetAlphabet[rem]

    # Reverse the string as output
    return out[::-1]

print convert("2015","0123456789","01")
