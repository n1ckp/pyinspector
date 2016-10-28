# Bubblesort algorithm
# See if you can reduce the number of execution steps!
def bubblesort(list_in, order="asc"):
    list_sorted = False
    end_index = len(list_in)-1
    while not list_sorted:
        # Set this flag to true at start of pass
        list_sorted = True
        for i in range(end_index): # Maximum value of i is (end_index - 1)
            # Sort Ascending
            if order == "asc" and list_in[i] > list_in[i+1]:
                list_sorted = False
                # Swap the values
                list_in[i], list_in[i+1] = list_in[i+1], list_in[i]
            # Sort Descending
            elif order == "desc" and list_in[i] < list_in[i+1]:
                list_sorted = False
                # Swap the values
                list_in[i], list_in[i+1] = list_in[i+1], list_in[i]
    return list_in

l = [4,8,2,3,9,1,2,0,3]
print(bubblesort(l, "asc"))
