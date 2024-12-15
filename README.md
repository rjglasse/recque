# Recursive Questioning

We begin with a multiple choice question ($Q0$) with three answering alternatives ($A1..A3$), as shown below. If the learner selects an incorrect answer (e.g. $A3$ of $Q0$), then a simpler question is generated ($Q1$), based on the underlying misconception. This becomes recursive if the learner answers this ($Q1$) and subsequent questions incorrectly ($Q2$ and beyond). Once they answer a question correctly (i.e.~a base case has been reached and the branch of recursion can unwind), they are given the chance to answer the previous question. Eventually, the learner will return to the original question and they will be able to progress to the next question ($QN$).

![Screenshot 2024-12-12 at 13 37 37](https://github.com/user-attachments/assets/8b60dc82-c913-4553-9f1a-84e96efb4e9f)

# Usage
This is a simple [implementation](https://github.com/rjglasse/recque/blob/main/recque.py) of the concept of RQ as a text-based interface. The only requirement is to have an `OPEN_AI_API_KEY` environment variable on your system with an active key. Running is as easy as:

```bash
$ python recque.py
```

And it only asks questions about basic math operations.

# Trace output
```
Question: In the expression 6 + 3 * 2 - 4, what is the correct order of evaluation that leads to the final result? Consider the standard precedence rules for addition, subtraction, and multiplication, as well as the left-to-right associativity for addition and subtraction. Choose the evaluation order that results in the correct final outcome.

(1) First evaluate 6 + 3, then 9 * 2, and finally 18 - 4.
(2) First evaluate 3 * 2, then 6 + 6, and finally 12 - 4.
(3) First evaluate 6 + 3, then 3 * 2, and finally 9 - 4.
(4) First evaluate 2 - 4, then 6 + (-2), and finally 4 * 3.

Enter a number: 1

That's incorrect :|
>> Let's try another question.

Question: Consider the expression 5 + 4 * 2. Which operation should be performed first to ensure the correct order of evaluation?

(1) Perform operations in the order they appear from left to right.
(2) Perform 5 + 4 first, then multiply the result by 2.
(3) Add 5 and 4 together, ignoring multiplication precedence.
(4) Perform 4 * 2 first, then add 5.

Enter a number: 2

That's incorrect :|
>> Let's try another question.

Question: Think about the expression 8 - 3 * 2. If you remember that multiplication is like a strong current in a river, should you swim with it first before trying to control where you go?

(1) Subtract 8 and 3 first, then multiply the result by 2.
(2) The order doesn't matter, as long as all operations are done.
(3) Operations should be completed from left to right, starting with subtraction.
(4) Perform 3 * 2 first, then subtract from 8.

Enter a number: 4

Correct! :)
>> Let's go back to the earlier question.

Question: Consider the expression 5 + 4 * 2. Which operation should be performed first to ensure the correct order of evaluation?

(1) Perform 5 + 4 first, then multiply the result by 2. (incorrect)
(2) Add 5 and 4 together, ignoring multiplication precedence.
(3) Perform 4 * 2 first, then add 5.
(4) Perform operations in the order they appear from left to right.

Enter a number: 3

Correct! :)
>> Let's go back to the earlier question.

Question: In the expression 6 + 3 * 2 - 4, what is the correct order of evaluation that leads to the final result? Consider the standard precedence rules for addition, subtraction, and multiplication, as well as the left-to-right associativity for addition and subtraction. Choose the evaluation order that results in the correct final outcome.

(1) First evaluate 3 * 2, then 6 + 6, and finally 12 - 4.
(2) First evaluate 6 + 3, then 9 * 2, and finally 18 - 4. (incorrect)
(3) First evaluate 2 - 4, then 6 + (-2), and finally 4 * 3.
(4) First evaluate 6 + 3, then 3 * 2, and finally 9 - 4.

Enter a number: 1

Correct! :)
Well done, you've completed all questions!
```
