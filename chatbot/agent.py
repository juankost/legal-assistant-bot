import os
import re
import requests
import json
from typing import Tuple, List

from omegaconf import OmegaConf

from pydantic import Field, BaseModel

from vectara_agentic.agent import Agent
from vectara_agentic.agent_config import AgentConfig
from vectara_agentic.tools import ToolsFactory, VectaraToolFactory
from vectara_agentic.tools_catalog import ToolsCatalog

from dotenv import load_dotenv

load_dotenv(override=True)

citation_description = """
    The citation for a particular case. 
    Citation must include the volume number, reporter, and first page. For example: 253 P.2d 136.
"""


def extract_components_from_citation(citation: str) -> dict:
    citation_components = citation.split(" ")
    volume_num = citation_components[0]
    reporter = "-".join(citation_components[1:-1]).replace(".", "").lower()
    first_page = citation_components[-1]

    if not volume_num.isdigit():
        return {}
    if not first_page.isdigit():
        return {}

    return {"volume": int(volume_num), "reporter": reporter, "first_page": int(first_page)}


class AgentTools:
    def __init__(self, _cfg, agent_config):
        self.tools_factory = ToolsFactory()
        self.agent_config = agent_config
        self.cfg = _cfg
        self.vec_factory = VectaraToolFactory(
            vectara_api_key=_cfg.api_key, vectara_corpus_key=_cfg.corpus_key
        )

    def get_opinion_text(
        self,
        case_citation: str = Field(description=citation_description),
        summarize: bool = Field(
            default=True,
            description="if True returns case summary, otherwise the full text of the case",
        ),
    ) -> str:
        """
        Returns the full opinion/ruling text of the case, or the summary if summarize=True.
        If there is more than one opinion for the case, the type of each opinion is returned with the text,
        and the opinions (or their summaries) are separated by semicolons (;)
        Args
            case_citation (str): the citation for a particular case. Citation must include the volume number, reporter, and first page. For example: 253 P.2d 136.
            summarize (bool): True to return just a summary of the case, False to return full case text.
        returns
            str: the full opinion/ruling text of the case, or the summary if summarize is True.
        """
        citation_dict = extract_components_from_citation(case_citation)
        if not citation_dict:
            return f"Citation is invalid: {case_citation}."
        summarize_text = ToolsCatalog(self.agent_config).summarize_text
        reporter = citation_dict["reporter"]
        volume_num = citation_dict["volume"]
        first_page = citation_dict["first_page"]
        response = requests.get(
            f"https://static.case.law/{reporter}/{volume_num}/cases/{first_page:04d}-01.json"
        )
        if response.status_code != 200:
            return f"Case not found; please check the citation {case_citation}."
        res = json.loads(response.text)

        if len(res["casebody"]["opinions"]) == 1:
            text = res["casebody"]["opinions"][0]["text"]
            output = text if not summarize else summarize_text(text, "law")
        else:
            output = ""
            for opinion in res["casebody"]["opinions"]:
                text = opinion["text"] if not summarize else summarize_text(opinion["text"], "law")
                output += f"Opinion type: {opinion['type']}, text: {text};"

        return output

    def get_case_document_pdf(
        self, case_citation: str = Field(description=citation_description)
    ) -> str:
        """
        Given a case citation, returns a valid web URL to a pdf of the case record
        Args:
            case_citation (str): the citation for a particular case. Citation must include the volume number, reporter, and first page. For example: 253 P.2d 136.
        Returns:
            str: a valid web URL to a pdf of the case record
        """
        citation_dict = extract_components_from_citation(case_citation)
        if not citation_dict:
            return f"Citation is invalid: {case_citation}."
        reporter = citation_dict["reporter"]
        volume_num = citation_dict["volume"]
        first_page = citation_dict["first_page"]
        response = requests.get(
            f"https://static.case.law/{reporter}/{volume_num}/cases/{first_page:04d}-01.json"
        )
        if response.status_code != 200:
            return f"Case not found; please check the citation {case_citation}."
        res = json.loads(response.text)
        page_number = res["first_page_order"]
        return f"https://static.case.law/{reporter}/{volume_num}.pdf#page={page_number}"

    def get_case_document_page(
        self, case_citation: str = Field(description=citation_description)
    ) -> str:
        """
        Given a case citation, returns a valid web URL to a page with information about the case.
        Args:
            case_citation (str): the citation for a particular case. Citation must include the volume number, reporter, and first page. For example: 253 P.2d 136.
        Returns:
            str: a valid web URL to a page with information about the case
        """
        citation_dict = extract_components_from_citation(case_citation)
        if not citation_dict:
            return f"Citation is invalid: {case_citation}."
        reporter = citation_dict["reporter"]
        volume_num = citation_dict["volume"]
        first_page = citation_dict["first_page"]
        url = f"https://case.law/caselaw/?reporter={reporter}&volume={volume_num}&case={first_page:04d}-01"
        response = requests.get(url)
        if response.status_code != 200:
            return "Case not found; please check the citation."
        return url

    def get_case_name(
        self, case_citation: str = Field(description=citation_description)
    ) -> Tuple[str, str]:
        """
        Given a case citation, returns its name and name abbreviation.
        Args:
            case_citation (str): the citation for a particular case. Citation must include the volume number, reporter, and first page. For example: 253 P.2d 136.
        Returns:
            Tuple[str, str]: the name and name abbreviation of the case
        """
        citation_dict = extract_components_from_citation(case_citation)
        if not citation_dict:
            return (
                f"Citation is invalid: {case_citation}.",
                f"Citation is invalid: {case_citation}.",
            )
        reporter = citation_dict["reporter"]
        volume_num = citation_dict["volume"]
        first_page = citation_dict["first_page"]
        response = requests.get(
            f"https://static.case.law/{reporter}/{volume_num}/cases/{first_page:04d}-01.json"
        )
        if response.status_code != 200:
            return "Case not found", "Case not found"
        res = json.loads(response.text)
        return res["name"], res["name_abbreviation"]

    def get_cited_cases(
        self, case_citation: str = Field(description=citation_description)
    ) -> List[dict]:
        """
        Given a case citation, returns a list of cases that are cited by the opinion of this case.
        Args:
            case_citation (str): the citation for a particular case. Citation must include the volume number, reporter, and first page. For example: 253 P.2d 136.
        Returns:
            A list of cases, each a dict with the citation, name and name_abbreviation of the case.
        """
        citation_dict = extract_components_from_citation(case_citation)
        if not citation_dict:
            return [f"Citation is invalid: {case_citation}."]
        reporter = citation_dict["reporter"]
        volume_num = citation_dict["volume"]
        first_page = citation_dict["first_page"]
        response = requests.get(
            f"https://static.case.law/{reporter}/{volume_num}/cases/{first_page:04d}-01.json"
        )
        if response.status_code != 200:
            return "Case not found; please check the citation."
        res = json.loads(response.text)
        citations = res["cites_to"]
        res = []
        for citation in citations[:10]:
            name, name_abbreviation = self.get_case_name(citation["cite"])
            res.append(
                {"citation": citation["cite"], "name": name, "name_abbreviation": name_abbreviation}
            )
        return res

    def validate_url(
        self, url: str = Field(description="A web url pointing to case-law document")
    ) -> str:
        """
        Given a url, returns whether or not the url is valid.
        Args:
            url (str): A web url pointing to case-law document
        Returns:
            str: "URL is valid" if the url is valid, "URL is invalid" otherwise.
        """
        pdf_pattern = re.compile(r"^https://static.case.law/.*")
        document_pattern = re.compile(r"^https://case.law/caselaw/?reporter=.*")
        return (
            "URL is valid"
            if pdf_pattern.match(url) or document_pattern.match(url)
            else "URL is invalid"
        )

    def get_tools(self):
        class QueryCaselawArgs(BaseModel):
            query: str = Field(..., description="The user query.")

        vec_factory = VectaraToolFactory(
            vectara_api_key=self.cfg.api_key, vectara_corpus_key=self.cfg.corpus_key
        )
        summarizer = "vectara-experimental-summary-ext-2023-12-11-med-omni"

        ask_caselaw = vec_factory.create_rag_tool(
            tool_name="ask_caselaw",
            tool_description="A tool for asking questions about case law in Alaska. ",
            tool_args_schema=QueryCaselawArgs,
            reranker="chain",
            rerank_k=100,
            rerank_chain=[
                {"type": "slingshot", "cutoff": 0.2},
                {"type": "mmr", "diversity_bias": 0.1},
                {
                    "type": "userfn",
                    "user_function": "max(1000 * get('$.score') - hours(seconds(to_unix_timestamp(now()) - to_unix_timestamp(datetime_parse(get('$.document_metadata.decision_date'), 'yyyy-MM-dd')))) / 24 / 365, 0)",
                },
            ],
            n_sentences_before=2,
            n_sentences_after=2,
            lambda_val=0.005,
            summary_num_results=15,
            vectara_summarizer=summarizer,
            include_citations=True,
        )

        return [ask_caselaw] + [
            self.tools_factory.create_tool(tool)
            for tool in [
                self.get_opinion_text,
                self.get_case_document_pdf,
                self.get_case_document_page,
                self.get_cited_cases,
                self.get_case_name,
                self.validate_url,
            ]
        ]


def get_agent_config() -> OmegaConf:
    cfg = OmegaConf.create(
        {
            "corpus_key": str(os.environ["VECTARA_CORPUS_KEY"]),
            "api_key": str(os.environ["VECTARA_API_KEY"]),
            "examples": os.environ.get("QUERY_EXAMPLES", None),
            "demo_name": "legal-agent",
            "demo_welcome": "Welcome to the Legal Assistant demo.",
            "demo_description": "This demo can help you prepare for a court case by providing you information about past court cases in Alaska.",
        }
    )
    return cfg


def initialize_agent(_cfg, agent_progress_callback=None):

    legal_assistant_instructions = """
    - You are a helpful legal assistant, with case law expertise in the state of Alaska.
    - Use the 'ask_caselaw' tool as your primary tool for answering user questions. Do not use your own knowledge to answer questions.
    - If the 'ask_caselaw' tool responds that it does not have enough information to answer the question,
      try to rephrase the query, or break the original query down into multiple sub-questions, and use the 'ask_caselaw' tool again.
    - The references returned by the 'ask_caselaw' tool include metadata relevant to its response, such as case citations, dates, or names.
    - When using a case citation in your response, try to include a valid URL along with it:
      * Call the 'get_case_document_pdf' for a case citation to obtain a valid web URL to a pdf of the case record.
      * If this doesn't work, call the 'get_case_document_page' for a case citation to obtain a valid web URL to a page with information about the case.
    - When including a URL for a citation in your response, use the citation as anchor text, and the URL as the link.
    - Never use your internal knowledge to guess a case citation. Only use citation information provided by a tool or the user.
    - A Case Citation includes 3 components: volume number, reporter, and first page. 
      Here are some examples: '253 P.2d 136', '10 Alaska 11', '6 C.M.A. 3'
    - If two cases have conflicting rulings, assume that the case with the more current ruling date is correct.
    - If the response is based on cases that are older than 5 years, make sure to inform the user that the information may be outdated,
      since some case opinions may no longer apply in law.
    - To summarize the case, use the 'get_opinion_text' with summarize=True.
    - Use 'get_opinion_text' with summarize=False only when full text is needed. Consider summarizing the text when possible to make things run faster.
    - If a user wants to test their argument, use the 'ask_caselaw' tool to gather information about cases related to their argument 
      and the 'critique_as_judge' tool to determine whether their argument is sound or has issues that must be corrected.
    - Never discuss politics, and always respond politely.
    - Your response should not include markdown.
    """
    agent_config = AgentConfig()

    agent = Agent(
        tools=AgentTools(_cfg, agent_config).get_tools(),
        topic="Case law in Alaska",
        custom_instructions=legal_assistant_instructions,
        agent_progress_callback=agent_progress_callback,
        agent_config=agent_config,
    )
    agent.report()
    return agent
