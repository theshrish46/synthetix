from state import AgentState
from prompts.structured_output_types import RefactorResults, ReviewResults

import os
import requests
import time

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from tools.github_tool import github_client

load_dotenv()

llm = ChatGroq(
    #model="mixtral-8x7b-32768",
    model="llama-3.3-70b-versatile",
    temperature=0.2
)


def discovery_node(state: AgentState) -> AgentState:
    print(f"This is discovery node state is")
    
    # So I already have the info about the Github repo owner and his repo inside the state dict which I can use to get the entire thing to the state dict using github client

    # Get the main repo
    repo_url = state['repo_url'].rstrip("/")
    parts = repo_url.split("/")
    owner = parts[-2]
    repo = parts[-1]


    # Get the default and other branches
    repo_obj = github_client.get_repo(f"{owner}/{repo}")
    default_branch = repo_obj.default_branch
    all_branches = repo_obj.get_branches()
    branche_names = [branch.name for branch in all_branches]


    # Get the tree structure
    tree = repo_obj.get_git_tree(default_branch, recursive=True)

    ALLOWED_EXTENSIONS = {".py", ".c", ".cpp", ".js", ".java", ".ts"}

    files_to_process = []
    full_tree_paths = []

    for item in tree.tree:
        full_tree_paths.append(item.path)


        if item.type == "blob":
            _, ext = os.path.splitext(item.path)

            if ext.lower() in ALLOWED_EXTENSIONS:
                files_to_process.append(item.path)


    return {
        **state,
        "repo_id": f"{owner}/{repo}",
        "base_branch": default_branch,
        "branches": branche_names,
        "file_tree": [item.path for item in tree.tree],
        "files_to_process": files_to_process,
    }


def selector_node(state: AgentState) -> AgentState:
    """
    So now i need to focus on things for this node
    
    - First select the queue file_to_process and take out the top most file to rocess

    - Update the queue containing everything except the first element

    - Fetch the raw code form the github using client

    - Return the path with a new updated 
        - files_to_process
        - current_file
        - repo_data having {
                original_code from github client
            }
    """
    print(f"This is inside selector node state is")
    
    on_focus_file = state["files_to_process"][0]
    remaining_files = state["files_to_process"][1:]
    repo = github_client.get_repo(state["repo_id"])

    raw_code = ""
    try:
        content_file = repo.get_contents(on_focus_file)

        if content_file.type == "file":
            raw_code = content_file.decoded_content.decode("utf-8")
        else:
            print(f"{on_focus_file} is a directory not a file")
    except Exception as e:
        print(f"Error accessing file {e}")

    return {
        **state,
        "current_file": on_focus_file,
        "files_to_process": remaining_files,
        "repo_data": {
            on_focus_file: {
                "original_code": raw_code,
                "status": "pending"
            }
        }
    }

def refractor_node(state: AgentState) -> AgentState:
    strutured_llm = llm.with_structured_output(RefactorResults)

    print(f"This is Refractor node state is")
    with open("prompts/refractor/refractor_system.txt", "r") as f:
        system_content = f.read()
    
    with open("prompts/refractor/refractor_human.txt", "r") as f:
        human_content = f.read()
    
    extension = state["current_file"].split(".")[-1]
    lang_map = {"py": "Python", "cpp": "C++", "c": "C", "js": "JavaScript"}
    current_lang = lang_map.get(extension, "Unknown")

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_content),
        ("human", human_content)
    ])

    final_prompt = prompt_template.format_messages(
        filename=state["current_file"],
        language=current_lang,
        original_code=state["repo_data"][state["current_file"]]["original_code"]
    )

    result = strutured_llm.invoke(final_prompt)

    return {
        **state,
        "repo_data": {
            state["current_file"]: {
                "original_code": state["repo_data"][state["current_file"]]["original_code"],
                "refactored_code": result.new_code,
                "status": "refactored",
                "commit_message": result.commit_message,
                "explanation": result.explanation
            }
        }
    }

def reviewer_node(state: AgentState) -> AgentState:
    print(f"Inside the reviewer node state is")


    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.2
    )
    structured_llm = llm.with_structured_output(ReviewResults)

    with open("prompts/reviewer/reviewer_system.txt", "r") as f:
        system_content = f.read()

    with open("prompts/reviewer/reviewer_human.txt", "r") as f:
        human_content = f.read()

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_content),
        ("human", human_content)
    ])


    final_prompt = prompt.format_messages(
        original_code=state["repo_data"][state["current_file"]]["original_code"],
        refactored_code=state["repo_data"][state["current_file"]]["refactored_code"]
    )

    result = structured_llm.invoke(final_prompt)
    return {
        **state,
        "repo_data": {
            state["current_file"]: {
                "original_code": state["repo_data"][state["current_file"]]["original_code"],
                "refactored_code": state["repo_data"][state["current_file"]]["refactored_code"],
                "status": state["repo_data"][state["current_file"]]["status"],
                "commit_message": state["repo_data"][state["current_file"]]["commit_message"],
                "explanation": state["repo_data"][state["current_file"]]["explanation"],
                "review": {
                    "score": result.score,
                    "feedback": result.feedback
                } 
            }
        }
    }

state = {
  "repo_url": "https://github.com/theshrish46/synthetix_test_repo",
  "repo_id": "theshrish46/synthetix_test_repo",
  "base_branch": "main",
  "branches": [
    "main",
    "new-branch"
  ],
  "file_tree": [
    "add.py",
    "mul.cpp",
    "sub.c",
    "test.txt",
    "test_dir",
    "test_dir/buggy.c",
    "test_dir/buggy.cpp",
    "test_dir/testython.py",
    "test_folder",
    "test_folder/another_dir",
    "test_folder/another_dir/testanother.c",
    "test_folder/buggy.java"
  ],
  "files_to_process": [],
  "current_file": "test_folder/buggy.java",
  "repo_data": {
    "add.py": {
      "original_code": "def addition(num1, num2):\n    return num1 + num2\n\ndef subtract(num1, num2):\n    return num1 + num2\n\ndef multiply(num1, num2):\n    return num + num2\n\ndef divide(num1, num2):\n    return num1 / num12\n",
      "refactored_code": "def addition(num1: int, num2: int) -> int:\n    return num1 + num2\n\ndef subtract(num1: int, num2: int) -> int:\n    return num1 - num2\n\ndef multiply(num1: int, num2: int) -> int:\n    return num1 * num2\n\ndef divide(num1: int, num2: int) -> float:\n    if num2 == 0:\n        raise ZeroDivisionError(\"Cannot divide by zero\")\n    return num1 / num2",
      "status": "refactored",
      "commit_message": "Fixed logical errors and improved type safety in arithmetic operations",
      "explanation": "The original code had incorrect operators, undefined variables, and type safety issues that were fixed to ensure correct arithmetic operations",
      "review": {
        "score": 9.0,
        "feedback": "The refactored code has significantly improved in terms of correctness, readability, and maintainability. However, there is still room for improvement, such as adding input validation for non-integer inputs."
      }
    },
    "mul.cpp": {
      "original_code": "#include<stdio.h>\n\nvoid main() {\n\n\tprintf(\"Multiplication function file\\n\");\n}\n",
      "refactored_code": "#include<iostream>\n\nint main() {\n    std::cout << \"Multiplication function file\" << std::endl;\n    return 0;\n}",
      "status": "refactored",
      "commit_message": "Refactored mul.cpp to improve type safety and fix syntax errors",
      "explanation": "Fixed the main function return type to int and included the correct header file for input/output operations",
      "review": {
        "score": 8.0,
        "feedback": "The refactored code has improved readability and maintainability by using the standard C++ library for input/output operations. However, it does not provide any multiplication functionality as suggested by the output message."
      }
    },
    "sub.c": {
      "original_code": "#include<stdio.h>\n\nvoid main(){\n\tint num1 = 5, num2 = 3;\n\tprintf(\"Subtraction is\\n \", num1 - num2);\n}\n",
      "refactored_code": "#include<stdio.h>\n\nint main(){\n    int num1 = 5, num2 = 3;\n    printf(\"Subtraction is: %d\\n\", num1 - num2);\n    return 0;\n}",
      "status": "refactored",
      "commit_message": "Fixed printf format specifier and return type of main function",
      "explanation": "The original code had a logical error in the printf format specifier and the return type of the main function was incorrect",
      "review": {
        "score": 9.0,
        "feedback": "The refactored code is improved, but the return type of main should be int and it should return an integer value. The printf statement is also corrected to include the subtraction result."
      }
    },
    "test_dir/buggy.c": {
      "original_code": "#include <stdio.h>\n#include <stdlib.h>\n#include <time.h>\n\nint generateNumbers(int* arr, int count) {\n  for (int i = 0; i <= count; i++) {  // off by one\n    arr[i] = rand() % 100;\n  }\n}\n\nfloat average(int* arr, int count) {\n  int sum = 0;\n\n  for (int i = 0; i < count; i++) {\n    sum += arr[i];\n  }\n\n  return sum / count;  // integer division\n}\n\nint findMax(int* arr, int count) {\n  int max = 0;\n\n  for (int i = 0; i < count; i++) {\n    if (arr[i] > max) max = arr[i];\n  }\n\n  return max;\n}\n\nint main() {\n  int count;\n\n  printf(\"How many numbers: \");\n  scanf(\"%d\", count);  // missing &\n\n  int* numbers = malloc(count * sizeof(int));\n\n  generateNumbers(numbers, count);\n\n  printf(\"Average: %f\\n\", average(numbers, count));\n  printf(\"Max: %d\\n\", findMax(numbers, count));\n\n  for (int i = 0; i <= count; i++) {\n    printf(\"%d\\n\", numbers[i]);\n  }\n\n  free(numbers);\n\n  return 0;\n}",
      "refactored_code": "#include <stdio.h>\n#include <stdlib.h>\n#include <time.h>\n\nint generateNumbers(int* arr, int count) {\n  for (int i = 0; i < count; i++) {\n    arr[i] = rand() % 100;\n  }\n  return 0;\n}\n\nfloat average(int* arr, int count) {\n  int sum = 0;\n  for (int i = 0; i < count; i++) {\n    sum += arr[i];\n  }\n  return (float)sum / count;\n}\n\nint findMax(int* arr, int count) {\n  int max = arr[0];\n  for (int i = 1; i < count; i++) {\n    if (arr[i] > max) max = arr[i];\n  }\n  return max;\n}\n\nint main() {\n  int count;\n  printf(\"How many numbers: \");\n  scanf(\"%d\", &count);\n  int* numbers = malloc(count * sizeof(int));\n  if (numbers == NULL) {\n    printf(\"Memory allocation failed\\n\");\n    return -1;\n  }\n  srand(time(NULL));\n  generateNumbers(numbers, count);\n  printf(\"Average: %f\\n\", average(numbers, count));\n  printf(\"Max: %d\\n\", findMax(numbers, count));\n  for (int i = 0; i < count; i++) {\n    printf(\"%d\\n\", numbers[i]);\n  }\n  free(numbers);\n  return 0;\n}",
      "status": "refactored",
      "commit_message": "Fixed off-by-one errors, integer division, and missing ampersand in scanf",
      "explanation": "The code had off-by-one errors in the generateNumbers function and the main function's for loop, integer division in the average function, and a missing ampersand in the scanf function call",
      "review": {
        "score": 9.0,
        "feedback": "The refactored code has significantly improved in terms of bug fixes, readability, and maintainability. The off-by-one error in the generateNumbers function has been fixed, and the average function now correctly performs floating-point division. The findMax function has been improved by initializing max with the first element of the array. Additionally, the code now checks for memory allocation failure and seeds the random number generator. However, there is still room for improvement, such as adding more error checking and handling for potential edge cases."
      }
    },
    "test_dir/buggy.cpp": {
      "original_code": "#include <cstdlib>\n#include <ctime>\n#include <iostream>\n#include <vector>\n\nusing namespace std;\n\nvector<int> generateNumbers(int count) {\n  vector<int> nums;\n\n  for (int i = 0; i <= count; i++) {  // off by one\n    nums.push_back(rand() % 100);\n  }\n\n  return nums;\n}\n\ndouble average(vector<int> nums) {\n  int sum = 0;\n\n  for (int i = 0; i < nums.size(); i++) {\n    sum += nums[i];\n  }\n\n  return sum / nums.size();  // integer division\n}\n\nint findMin(vector<int> nums) {\n  int m = nums[0];\n\n  for (int i = 0; i <= nums.size(); i++) {\n    if (nums[i] < m) m = nums[i + 1];  // index bug\n  }\n\n  return m;\n}\n\nint main() {\n  int count;\n\n  cout << \"How many numbers: \";\n  cin >> count;\n\n  vector<int> numbers = generateNumbers(count);\n\n  cout << \"Average: \" << average(numbers) << endl;\n  cout << \"Min: \" << findMin(numbers) << endl;\n\n  for (int i = 0; i <= numbers.size(); i++) {\n    cout << numbers[i] << endl;\n  }\n\n  return 0;\n}",
      "refactored_code": "#include <cstdlib>\n#include <ctime>\n#include <iostream>\n#include <vector>\n\nusing namespace std;\n\n// Function to generate 'count' number of random numbers between 0 and 100\nvector<int> generateNumbers(int count) {\n  vector<int> nums;\n  srand(time(0)); // seed for random number generation\n  for (int i = 0; i < count; i++) {\n    nums.push_back(rand() % 100);\n  }\n  return nums;\n}\n\ndouble average(const vector<int>& nums) {\n  int sum = 0;\n  for (int num : nums) {\n    sum += num;\n  }\n  return static_cast<double>(sum) / nums.size();\n}\n\nint findMin(const vector<int>& nums) {\n  int m = nums[0];\n  for (int i = 1; i < nums.size(); i++) {\n    if (nums[i] < m) m = nums[i];\n  }\n  return m;\n}\n\nint main() {\n  int count;\n  cout << \"How many numbers: \";\n  cin >> count;\n  vector<int> numbers = generateNumbers(count);\n  cout << \"Average: \" << average(numbers) << endl;\n  cout << \"Min: \" << findMin(numbers) << endl;\n  for (int i = 0; i < numbers.size(); i++) {\n    cout << numbers[i] << endl;\n  }\n  return 0;\n}",
      "status": "refactored",
      "commit_message": "Fixed logical bugs and improved code quality in buggy.cpp",
      "explanation": "Fixed off-by-one errors, integer division, and index bugs in the generateNumbers, average, and findMin functions",
      "review": {
        "score": 9.0,
        "feedback": "The refactored code has improved significantly in terms of readability, structure, and maintainability. The use of const references, range-based for loops, and static casting have enhanced the code quality. However, there is still room for improvement, such as adding error handling for cases like empty input vectors."
      }
    },
    "test_dir/testython.py": {
      "original_code": "import random\nimport time\n\ndef generate_numbers(count):\n    numbers = []\n    for i in range(count):\n        n = random.randint(1, 100)\n        numbers.append(n)\n    return numbers\n\ndef calculate_average(nums):\n    total = 0\n    for n in nums:\n        total += n\n    avg = total / len(nums)\n    return avg\n\ndef find_max(nums):\n    max_num = 0\n    for n in nums:\n        if n > max_num:\n            max_num = n\n    return max_num\n\ndef print_report(nums):\n    print(\"Numbers:\", nums)\n    print(\"Average:\", calculate_average(nums))\n    print(\"Max:\", find_max(nums))\n    print(\"Min:\", min_number(nums))\n\ndef min_number(nums):\n    m = nums[0]\n    for i in range(len(nums)):\n        if nums[i] < m:\n            m = nums[i+1]\n    return m\n\ndef main():\n    count = input(\"How many numbers to generate? \")\n    numbers = generate_numbers(count)\n\n    time.sleep(1)\n\n    print_report(numbers)\n\n    for i in range(5):\n        print(\"Random pick:\", numbers[random.randint(0, len(numbers))])\n\n    if calculate_average(numbers) > 50:\n        print(\"High average!\")\n    else\n        print(\"Low average!\")\n\nmain()",
      "refactored_code": "import random\nimport time\nfrom typing import List\n\ndef generate_numbers(count: int) -> List[int]:\n    numbers = [random.randint(1, 100) for _ in range(count)]\n    return numbers\n\ndef calculate_average(nums: List[int]) -> float:\n    return sum(nums) / len(nums)\n\ndef find_max(nums: List[int]) -> int:\n    return max(nums)\n\ndef min_number(nums: List[int]) -> int:\n    return min(nums)\n\ndef print_report(nums: List[int]) -> None:\n    print(\"Numbers:\", nums)\n    print(\"Average:\", calculate_average(nums))\n    print(\"Max:\", find_max(nums))\n    print(\"Min:\", min_number(nums))\n\ndef main() -> None:\n    while True:\n        try:\n         \r\n   count = int(input(\"How many numbers to generate? \"))\n            if count <= 0:\n                raise ValueError\n            break\n        except ValueError:\n            print(\"Please enter a positive integer.\")\n    numbers = generate_numbers(count)\n    time.sleep(1)\n    print_report(numbers)\n    for _ in range(5):\n        print(\"Random pick:\", random.choice(numbers))\n    if calculate_average(numbers) > 50:\n        print(\"High average!\")\n    else:\n        print(\"Low average!\")\n\ndef main_wrapper() -> None:\n    try:\n        main()\n    except Exception as e:\n        print(f\"An error occurred: {e}\")\n\ndef test_min_number() -> None:\n    numbers = [5, 2, 8, 12, 3]\n    assert min_number(numbers) == 2\n\ndef test_calculate_average() -> None:\n    numbers = [5, 2, 8, 12, 3]\n    assert calculate_average(numbers) == sum(numbers) / len(numbers)\n\ntest_min_number()\ntest_calculate_average()\nmain_wrapper()",
      "status": "refactored",
      "commit_message": "Refactored testython.py to fix logical bugs, improve type safety, and enhance PEP8 compliance",
      "explanation": "Fixed bugs in min_number function, added type hints, and corrected syntax errors in the main function",
      "review": {
        "score": 9.0,
        "feedback": "The refactored code is significantly improved with better structure, readability, and maintainability. It uses list comprehensions, built-in functions, and type hints. However, there are a few minor issues, such as the missing error handling for the time.sleep function and the redundant main_wrapper function."
      }
    },
    "test_folder/another_dir/testanother.c": {
      "original_code": "#include<stdio.h>\n\nvoid main\nprintf(hello world)\n",
      "refactored_code": "#include<stdio.h>\n\nint main() {\n    printf(\"hello world\");\n    return 0;\n}",
      "status": "refactored",
      "commit_message": "Fixed syntax errors and improved code readability in testanother.c",
      "explanation": "Fixed syntax errors, undefined variables, and improved code readability by adding proper function signature and including necessary standard library",
      "review": {
        "score": 9.0,
        "feedback": "The refactored code is much improved, with proper function signature and return type. However, it would be better to include a newline character at the end of the printf statement for consistency."
      }
    },
    "test_folder/buggy.java": {
      "original_code": "import java.util.Random;\nimport java.util.Scanner;\n\npublic class BuggyProgram {\n\n    public static int[] generateNumbers(int count) {\n        Random rand = new Random();\n        int[] nums = new int[count];\n\n        for(int i = 0; i <= count; i++) { // off by one\n            nums[i] = rand.nextInt(100);\n        }\n\n        return nums;\n    }\n\n    public static double average(int[] arr) {\n        int sum = 0;\n\n        for(int i = 0; i < arr.length; i++) {\n            sum += arr[i];\n        }\n\n        return sum / arr.length; // integer division bug\n    }\n\n    public static int findMax(int[] arr) {\n        int max = 0;\n\n        for(int i = 0; i < arr.length; i++) {\n            if(arr[i] > max)\n                max = arr[i];\n        }\n\n        return max;\n    }\n\n    public static void main(String[] args) {\n\n        Scanner sc = new Scanner(System.in);\n\n        System.out.print(\"How many numbers: \");\n        int count = sc.nextLine(); // wrong method\n\n        int[] numbers = generateNumbers(count);\n\n        System.out.println(\"Average: \" + average(numbers));\n        System.out.println(\"Max: \" + findMax(numbers));\n\n        for(int i = 0; i <= numbers.length; i++) {\n            System.out.println(numbers[i]);\n        }\n\n        sc.close();\n    }\n}",
      "refactored_code": "import java.util.Random; import java.util.Scanner; public class BuggyProgram {     public static int[] generateNumbers(int count) {         Random rand = new Random();         int[] nums = new int[count];         for(int i = 0; i < count; i++) {             nums[i] = rand.nextInt(100);         }         return nums;     }     public static double average(int[] arr) {         int sum = 0;         for(int i = 0; i < arr.length; i++) {             sum += arr[i];         }         return (double) sum / arr.length;     }     public static int findMax(int[] arr) {         int max = arr[0];         for(int i = 1; i < arr.length; i++) {             if(arr[i] > max)                 max = arr[i];         }         return max;     }     public static void main(String[] args) {         Scanner sc = new Scanner(System.in);         System.out.print(\"How many numbers: \");         int count = Integer.parseInt(sc.nextLine());         int[] numbers = generateNumbers(count);         System.out.println(\"Average: \" + average(numbers));         System.out.println(\"Max: \" + findMax(numbers));         for(int i = 0; i < numbers.length; i++) {             System.out.println(numbers[i]);         }         sc.close();     } }",
      "status": "refactored",
      "commit_message": "Fixed logical bugs, improved type safety, and enhanced code readability",
      "explanation": "The original code had off-by-one errors, integer division bugs, and incorrect method usage, which have been fixed and improved for better performance and maintainability",
      "review": {
        "score": 8.0,
        "feedback": "The refactored code has fixed the off-by-one error, integer division bug, and wrong method for getting user input. However, it can still be improved by handling potential exceptions and edge cases."
      }
    }
  }
}

def pr_manager(state: AgentState) -> AgentState:
    print(f"Inside the manager")

    # 1. Get the github repo using the repo id in state for further functionalities
    repo = github_client.get_repo(state["repo_id"])


    # 2. Create a unique branch, right now using time for simplicity but should improve in the future 
    new_branch = f"ai-refactor-{int(time.time())}"
    base_sha = repo.get_branch(state["base_branch"]).commit.sha
    repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=base_sha)

    # 3. Creating commit and raising pr 
    # 3.1 Creating the payload for request

    for path, data in state["repo_data"].items():
        if "refactored_code" in data:
            file_content = repo.get_contents(path=path, ref=state["base_branch"])
            repo.update_file(
                path=path,
                message=data["commit_message"],
                content=data["refactored_code"],
                sha=file_content.sha,
                branch=new_branch
            )
    
    # 4. Create a pull request and raise it
    pr = repo.create_pull(
        title="AI Refactor: Improvements & Bug Fixes",
        body=f"Refactored files :\n " + "\n".join([f"- {k} : {v["explanation"]}" for k, v in state["repo_data"].items() if "explanation" in v]),
        head=new_branch,
        base=state["base_branch"],
    )


    return {
        "pr_url": pr.html_url
    }