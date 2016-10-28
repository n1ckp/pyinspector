# Euclidean algorithm for finding the greatest common denominator (GCD)
# for two given numbers: num_a and num_b
def euclid(num_a, num_b):
    remainder = num_b
    while(remainder > 0):
        remainder = num_a % num_b
        if(remainder > 0):
            num_a = num_b
            num_b = remainder
    return num_b

print(euclid(252, 105))
