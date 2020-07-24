// Implements an array-based, integer deque

class IntegerArrayDeque
{
private:
    unsigned long* deque; // The deque itself
    short lastItemIndex, latestItemIndex;
    unsigned short size;
    unsigned short cnt;

public:
    IntegerArrayDeque(unsigned short size)
    {
        // Create the deque
        deque = (unsigned long*)malloc(size * sizeof(unsigned long));
        this->size = size;

        this->reset();
    }

    ~IntegerArrayDeque()
    {
        // Free the array
        free(deque);
    }

    // Put an item at the top of the deque
    void put(unsigned long item)
    {
        // Get the new insert index
        latestItemIndex = (latestItemIndex + 1) % size;

        // Insert the element
        deque[latestItemIndex] = item;

        // Increment the counter
        ++cnt;

        // Update lastItemIndex
        if (cnt == size + 1)
        {
            lastItemIndex = (lastItemIndex + 1) % size;
            --cnt;
        }
    }

    // Get the last item from this deque without removing it
    unsigned long get()
    {
        // If there are no items, return 0
        if (!cnt)
            return 0;

        return deque[lastItemIndex];
    }

    // Returns the latest item to be put into the deque
    unsigned long getFromTop()
    {
        if (!cnt)
            return 0;

        return deque[latestItemIndex];
    }

    // Remove the last item in this deque
    void pop()
    {
        // If empty, return
        if (!cnt)
            return;

        // Update the index
        lastItemIndex = (lastItemIndex + 1) % size;

        // Update the counter
        --cnt;
    }

    // Returns how many items are in the deque
    unsigned short count()
    {
        return cnt;
    }

    // Returns true if the deque is full, false otherwise
    bool isFull()
    {
        return cnt == size;
    }

    void reset()
    {
        lastItemIndex = 0;
        latestItemIndex = -1;
        cnt = 0;
    }
};