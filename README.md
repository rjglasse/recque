# Recursive Questioning

We begin with a multiple choice question ($Q0$) with three answering alternatives ($A1..A3$), as shown below. If the learner selects an incorrect answer (e.g.~$A3$ of $Q0$), then a simpler question is generated ($Q1$), based on the underlying misconception. This becomes recursive if the learner answers this ($Q1$) and subsequent questions incorrectly ($Q2$ and beyond). Once they answer a question correctly (i.e.~a base case has been reached and the branch of recursion can unwind), they are given the chance to answer the previous question. Eventually, the learner will return to the original question and they will be able to progress to the next question ($QN)$.

![Screenshot 2024-12-12 at 13 37 37](https://github.com/user-attachments/assets/8b60dc82-c913-4553-9f1a-84e96efb4e9f)

# recque
This is a simple implementation of the concept of RQ as a text-based interface.

# trace output
```
Question: What is a primary theme explored in Moby Dick?
(1) The struggle between man and nature
(2) The value of friendship and human connection
(3) The importance of technology in society
Enter a number: 2
That's incorrect.
Let's simplify the question.

Question: What struggle is a major part of the story in Moby Dick?
(1) The struggle for power within a community
(2) The struggle between man and nature
(3) The struggle for money and wealth
Enter a number: 1
That's incorrect.
Let's simplify the question.

Question: What does Captain Ahab struggle against in Moby Dick?
(1) The laws of the ocean
(2) A giant whale named Moby Dick
(3) His crew members' decisions
Enter a number: 2
Correct!
Let's go back to the earlier question.

Question: What struggle is a major part of the story in Moby Dick?
(1) The struggle for power within a community
(2) The struggle for money and wealth
(3) The struggle between man and nature
Enter a number: 3
Correct!
Let's go back to the earlier question.

Question: What is a primary theme explored in Moby Dick?
(1) The importance of technology in society
(2) The value of friendship and human connection
(3) The struggle between man and nature
Enter a number: 1
That's incorrect.
Let's simplify the question.

Question: What does the whale in Moby Dick represent in relation to nature?
(1) A symbol of friendship
(2) The challenge and power of nature
(3) A technological advancement
Enter a number: 2
Correct!
Let's go back to the earlier question.

Question: What is a primary theme explored in Moby Dick?
(1) The struggle between man and nature
(2) The value of friendship and human connection
(3) The importance of technology in society
Enter a number: 1
Correct!
Well done, you've completed all questions!
```
