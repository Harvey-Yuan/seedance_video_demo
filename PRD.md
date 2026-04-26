我现在希望搭建一个多agent协作flow。可以输入一个personal drama，输出一个视频。


1.user journey
有三个agent扮演三个layer的功能：

layer1:输入personal drama，输出一个三分钟视频故事分镜/脚本/角色和台词

layer2:输入layer1的input，然后输出动漫风格角色原画和给seedance2.0用的prompt

layer3:输入layer1，2的输出，然后输出一个video

LLM提供：

layer3 的seedance模型用/Users/harvey/Desktop/MY_project/seedance/seedance_video.py

layer1可以用来自butterbase的LLM模型

layer2可以用来自butterbase的LLM模型，但是也要用到生成图片的多模态模型


2.前端，用frontend-design设计

3.后端，用butterbase MCP 搞定