# Recursive Questioning

We begin with a multiple choice question ($Q0$) with three answering alternatives ($A1..A3$), as shown below. If the learner selects an incorrect answer (e.g.~$A3$ of $Q0$), then a simpler question is \textit{generated} ($Q1$), based on the underlying misconception. This becomes recursive if the learner answers this ($Q1$) and subsequent questions incorrectly ($Q2$ and beyond). Once they answer a question correctly (i.e.~a base case has been reached and the branch of recursion can unwind), they are given the chance to answer the previous question. Eventually, the learner will return to the original question and they will be able to progress to the next question ($QN)$.

![Screenshot 2024-12-12 at 13 37 37](https://github.com/user-attachments/assets/8b60dc82-c913-4553-9f1a-84e96efb4e9f)

# recque
This is a simple implementation of the concept of RQ as a text-based interface.
